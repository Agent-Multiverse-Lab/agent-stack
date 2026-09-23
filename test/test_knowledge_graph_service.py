"""知识图谱查询与实体检索服务测试。"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from server.service import knowledge_service


class FakeSession:
    """无事务边界需求的最小会话。"""

    async def commit(self) -> None:
        """记录提交。"""

    async def rollback(self) -> None:
        """记录回滚。"""


class FakeKnowledgeBaseRepository:
    """返回固定知识库。"""

    def __init__(self, *, exists=True) -> None:
        self.exists = exists

    async def get_for_user(self, **kwargs):
        """返回用户知识库。"""
        if not self.exists:
            return None
        return SimpleNamespace(kb_id=kwargs["kb_id"])


class FakeGraphStore:
    """返回固定节点与边。"""

    async def get_graph(self, *, kb_id):
        """返回两个节点一条边。"""
        return {
            "nodes": [
                {
                    "entity_id": "e1",
                    "name": "OpenAI",
                    "type": "组织",
                    "description": "AI 公司",
                    "file_id": "f1",
                },
                {
                    "entity_id": "e2",
                    "name": "GPT",
                    "type": "产品",
                    "description": "模型",
                    "file_id": "f1",
                },
            ],
            "edges": [
                {
                    "relation_id": "r1",
                    "source_entity_id": "e1",
                    "target_entity_id": "e2",
                    "type": "发布",
                }
            ],
        }


class FakeBindingRepository:
    """返回固定 Embedding 绑定。"""

    async def get(self, *, uid, kb_id):
        """返回测试绑定。"""
        return SimpleNamespace(
            kb_id=kb_id,
            collection_name="kb_collection",
            embedding_model_spec="mock/model",
            embedding_dimension=3,
            embedding_batch_size=8,
        )


class FakeEmbeddingService:
    """返回固定维度查询向量。"""

    async def embed_query(self, query: str) -> list[float]:
        """返回三维向量。"""
        return [1.0, 2.0, 3.0]


class FakeEntityStore:
    """返回固定实体命中。"""

    def __init__(self) -> None:
        self.search_vectors = []

    async def search_entities(self, *, collection_name, vector, limit):
        """记录查询向量并返回命中。"""
        self.search_vectors.append((collection_name, vector, limit))
        return [
            {
                "id": "e1",
                "distance": 0.93,
                "entity": {
                    "name": "OpenAI",
                    "entity_type": "组织",
                    "description": "AI 公司",
                    "file_id": "f1",
                },
            }
        ]


class KnowledgeGraphServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_get_graph_maps_nodes_and_edges(self) -> None:
        """图谱查询返回节点边及统计数量。"""
        with (
            patch.object(
                knowledge_service,
                "KnowledgeBaseRepository",
                return_value=FakeKnowledgeBaseRepository(),
            ),
            patch.object(
                knowledge_service,
                "get_graph_store",
                return_value=FakeGraphStore(),
            ),
        ):
            result = await knowledge_service.get_graph(
                FakeSession(),
                uid="user-1",
                kb_id="kb-1",
            )

        self.assertEqual(2, result["entity_count"])
        self.assertEqual(1, result["relation_count"])
        self.assertEqual("OpenAI", result["nodes"][0]["name"])
        self.assertEqual("e1", result["edges"][0]["source_entity_id"])

    async def test_get_graph_rejects_unknown_knowledge_base(self) -> None:
        """不存在或不属于当前用户的知识库不可读图谱。"""
        with patch.object(
            knowledge_service,
            "KnowledgeBaseRepository",
            return_value=FakeKnowledgeBaseRepository(exists=False),
        ):
            with self.assertRaisesRegex(LookupError, "知识库不存在"):
                await knowledge_service.get_graph(
                    FakeSession(),
                    uid="user-1",
                    kb_id="kb-9",
                )

    async def test_search_entities_maps_hits_with_similarity(self) -> None:
        """实体检索返回带相似度的命中映射。"""
        entity_store = FakeEntityStore()
        with (
            patch.object(
                knowledge_service,
                "KnowledgeEmbeddingBindingRepository",
                return_value=FakeBindingRepository(),
            ),
            patch.object(
                knowledge_service,
                "_create_embedding_service",
                return_value=(FakeEmbeddingService(), "mock/model", 2),
            ),
            patch.object(
                knowledge_service,
                "_get_knowledge",
                return_value=entity_store,
            ),
        ):
            result = await knowledge_service.search_entities(
                FakeSession(),
                uid="user-1",
                kb_id="kb-1",
                query="OpenAI",
                limit=20,
            )

        self.assertEqual(1, len(result["hits"]))
        self.assertEqual("e1", result["hits"][0]["entity_id"])
        self.assertAlmostEqual(0.93, result["hits"][0]["similarity"])
        self.assertEqual("OpenAI", result["hits"][0]["name"])
        collection_name = entity_store.search_vectors[0][0]
        self.assertEqual(
            knowledge_service._entity_collection_name("user-1", "kb-1"),
            collection_name,
        )


if __name__ == "__main__":
    unittest.main()
