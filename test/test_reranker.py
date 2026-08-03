"""通用 Reranker、DashScope 适配器和知识检索接入测试。"""

import json
import unittest
from collections.abc import Sequence
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from server.service import knowledge_service as knowledge_service_module
from server.service.knowledge_service import KnowledgeService
from src.configs import config as sys_config
from src.model import (
    BaseReranker,
    DashScopeReranker,
    RerankDocument,
    RerankError,
    load_reranker,
)


class FakeReranker(BaseReranker):
    """返回测试指定的候选索引和分数。"""

    def __init__(self, scores: Sequence[tuple[int, float]]) -> None:
        self.scores = scores

    async def _score(
        self,
        query: str,
        documents: Sequence[RerankDocument],
        *,
        top_n: int,
    ) -> Sequence[tuple[int, float]]:
        """返回前 top_n 个预设分数。"""
        return self.scores[:top_n]


class BaseRerankerTest(unittest.IsolatedAsyncioTestCase):
    """验证通用输入、输出和稳定排序。"""

    async def test_sorts_provider_scores_and_preserves_documents(
        self,
    ) -> None:
        """Provider 乱序结果应按分数和原始排名稳定排序。"""
        documents = [
            RerankDocument(id="a", text="A", original_rank=1),
            RerankDocument(id="b", text="B", original_rank=2),
            RerankDocument(id="c", text="C", original_rank=3),
        ]
        reranker = FakeReranker([(0, 0.4), (2, 0.9), (1, 0.9)])

        results = await reranker.arerank(
            "query",
            documents,
            top_n=3,
        )

        self.assertEqual(["b", "c", "a"], [
            result.document.id for result in results
        ])
        self.assertEqual([1, 2, 3], [
            result.rerank_rank for result in results
        ])

    async def test_rejects_duplicate_documents_and_invalid_provider_index(
        self,
    ) -> None:
        """重复业务 ID 和越界 Provider 索引必须失败。"""
        duplicate_documents = [
            RerankDocument(id="same", text="A", original_rank=1),
            RerankDocument(id="same", text="B", original_rank=2),
        ]
        with self.assertRaisesRegex(ValueError, "ID 重复"):
            await FakeReranker([(0, 1.0)]).arerank(
                "query",
                duplicate_documents,
                top_n=1,
            )

        with self.assertRaisesRegex(RerankError, "非法文档索引"):
            await FakeReranker([(2, 1.0)]).arerank(
                "query",
                [RerankDocument(id="a", text="A", original_rank=1)],
                top_n=1,
            )


class DashScopeRerankerTest(unittest.IsolatedAsyncioTestCase):
    """验证 DashScope 请求和响应适配。"""

    async def test_sends_expected_payload_and_maps_response_indices(
        self,
    ) -> None:
        """适配器应只发送文本，并使用本地候选恢复业务字段。"""
        captured: dict[str, object] = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            captured["authorization"] = request.headers["Authorization"]
            captured["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"index": 0, "relevance_score": 0.25},
                        {"index": 1, "relevance_score": 0.95},
                    ],
                    "id": "request-1",
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            reranker = DashScopeReranker(
                model="qwen3-rerank",
                api_key="test-key",
                endpoint="https://example.com/reranks",
                client=client,
            )
            results = await reranker.arerank(
                "  user query  ",
                [
                    RerankDocument(
                        id="chunk-a",
                        text="text a",
                        original_rank=1,
                        metadata={"file_id": "file-a"},
                    ),
                    RerankDocument(
                        id="chunk-b",
                        text="text b",
                        original_rank=2,
                        metadata={"file_id": "file-b"},
                    ),
                ],
                top_n=2,
            )

        self.assertEqual("Bearer test-key", captured["authorization"])
        self.assertEqual(
            {
                "model": "qwen3-rerank",
                "query": "user query",
                "documents": ["text a", "text b"],
                "top_n": 2,
            },
            captured["payload"],
        )
        self.assertEqual(
            ["chunk-b", "chunk-a"],
            [result.document.id for result in results],
        )
        self.assertEqual(
            "file-b",
            results[0].document.metadata["file_id"],
        )

    async def test_converts_http_status_without_leaking_body(self) -> None:
        """HTTP 错误只暴露状态码和请求 ID。"""

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                429,
                headers={"x-request-id": "request-429"},
                json={"message": "sensitive provider body"},
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            reranker = DashScopeReranker(
                model="qwen3-rerank",
                api_key="test-key",
                endpoint="https://example.com/reranks",
                client=client,
            )
            with self.assertRaisesRegex(
                RerankError,
                "status=429，request_id=request-429",
            ) as context:
                await reranker.arerank(
                    "query",
                    [RerankDocument(id="a", text="A", original_rank=1)],
                    top_n=1,
                )

        self.assertNotIn("sensitive provider body", str(context.exception))

    def test_loader_uses_rerank_environment_fields(self) -> None:
        """统一构造入口应从配置读取 API Key、URL 和超时。"""
        with (
            patch.object(sys_config, "rerank_model", "dashscope/qwen3-rerank"),
            patch.object(sys_config, "dashscope_api_key", "test-key"),
            patch.object(
                sys_config,
                "dashscope_rerank_url",
                "https://example.com/reranks",
            ),
            patch.object(
                sys_config,
                "rerank_request_timeout_seconds",
                12.0,
            ),
        ):
            reranker = load_reranker()

        self.assertIsInstance(reranker, DashScopeReranker)
        self.assertEqual("https://example.com/reranks", reranker.endpoint)
        self.assertEqual(12.0, reranker.request_timeout)


class FakeEmbeddingService:
    """返回固定查询向量。"""

    async def embed_query(self, query: str) -> list[float]:
        """生成测试向量。"""
        return [1.0, 2.0, 3.0]


class FakeKnowledge:
    """记录初召回数量并返回两个 Milvus 命中。"""

    def __init__(self) -> None:
        self.limit = 0

    async def search(
        self,
        *,
        collection_name: str,
        vector: list[float],
        limit: int,
    ) -> list[dict[str, object]]:
        """返回固定候选。"""
        self.limit = limit
        return [
            {
                "id": "chunk-a",
                "distance": 0.9,
                "entity": {
                    "chunk_id": "chunk-a",
                    "chunk": "text a",
                    "file_id": "file-a",
                    "chunk_index": 0,
                    "metadata": {"title": "A"},
                },
            },
            {
                "id": "chunk-b",
                "distance": 0.8,
                "entity": {
                    "chunk_id": "chunk-b",
                    "chunk": "text b",
                    "file_id": "file-b",
                    "chunk_index": 1,
                    "metadata": {"title": "B"},
                },
            },
        ]


class FakeBindingRepository:
    """返回固定知识库 Embedding 绑定。"""

    async def get(self, *, uid: str, kb_id: str) -> SimpleNamespace:
        """返回测试绑定。"""
        return SimpleNamespace(
            kb_id=kb_id,
            collection_name="collection",
            embedding_model_spec="mock/embedding",
            embedding_dimension=3,
            embedding_batch_size=2,
        )


class KnowledgeServiceRerankTest(unittest.IsolatedAsyncioTestCase):
    """验证知识检索的初召回与最终重排边界。"""

    async def test_search_reranks_candidates_and_preserves_scores(
        self,
    ) -> None:
        """服务应扩大初召回并返回带双分数的最终结果。"""
        knowledge = FakeKnowledge()
        service = KnowledgeService(
            SimpleNamespace(),
            storage=SimpleNamespace(),
            pipeline=SimpleNamespace(),
        )
        service.bindings = FakeBindingRepository()
        service._knowledge = knowledge
        service._reranker = FakeReranker([(0, 0.2), (1, 0.95)])
        service._create_embedding_service = lambda *args, **kwargs: (
            FakeEmbeddingService(),
            "mock/embedding",
            2,
        )

        with (
            patch.object(
                knowledge_service_module.sys_config,
                "rerank_model",
                "dashscope/qwen3-rerank",
            ),
            patch.object(
                knowledge_service_module.sys_config,
                "rerank_candidate_limit",
                50,
            ),
        ):
            result = await service.search(
                uid="user-1",
                kb_id="kb-1",
                query="query",
                limit=2,
            )

        self.assertEqual(50, knowledge.limit)
        self.assertEqual(
            ["chunk-b", "chunk-a"],
            [hit["id"] for hit in result["hits"]],
        )
        self.assertEqual(0.8, result["hits"][0]["distance"])
        self.assertEqual(2, result["hits"][0]["retrieval_rank"])
        self.assertEqual(0.95, result["hits"][0]["rerank_score"])
        self.assertEqual(1, result["hits"][0]["rerank_rank"])
        self.assertEqual(
            {
                "applied": True,
                "model_spec": "dashscope/qwen3-rerank",
                "candidate_count": 2,
                "result_count": 2,
            },
            result["rerank"],
        )


if __name__ == "__main__":
    unittest.main()
