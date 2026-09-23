"""知识图谱抽取服务测试。"""

import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from server.service import knowledge_service
from src.knowledge.graph import GraphExtractionResult


class FakeSession:
    """记录抽取流程的事务行为。"""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        """记录事务提交。"""
        self.commits += 1

    async def rollback(self) -> None:
        """记录事务回滚。"""
        self.rollbacks += 1


class FakeKnowledgeFileRepository:
    """在内存中维护知识文件状态。"""

    def __init__(self, *, status="indexed") -> None:
        self.file = SimpleNamespace(
            file_id="file-1",
            kb_id="kb-1",
            original_file_name="manual.pdf",
            markdown_object_name="parsed/document.md",
            status=status,
            error_message=None,
        )

    async def get_for_user(self, **kwargs):
        """返回测试知识文件。"""
        return self.file

    async def update_status(
        self,
        file_record,
        *,
        status,
        markdown_object_name=None,
        error_message=None,
    ):
        """更新测试知识文件状态。"""
        file_record.status = status
        file_record.error_message = error_message
        return file_record


class FakeStorage:
    """返回固定已解析 Markdown。"""

    async def adownload_file(self, bucket_name: str, object_name: str) -> bytes:
        """下载测试 Markdown。"""
        return b"# Title\n\nBody"


class FakeBindingRepository:
    """返回固定 Embedding 绑定。"""

    async def get(self, *, uid: str, kb_id: str):
        """返回测试绑定。"""
        return SimpleNamespace(
            kb_id=kb_id,
            collection_name="kb_collection",
            embedding_model_spec="mock/model",
            embedding_dimension=3,
            embedding_batch_size=8,
        )


class FakeEmbeddingService:
    """返回固定维度向量。"""

    dimension = 3

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """为每个实体名生成三维向量。"""
        return [[1.0, 2.0, 3.0] for _ in texts]


class FakeExtractor:
    """返回固定抽取结果，可注入失败。"""

    def __init__(self, result=None, error=None) -> None:
        self.result = result
        self.error = error

    async def extract(self, markdown: str):
        """返回抽取结果或抛出异常。"""
        if self.error is not None:
            raise self.error
        return self.result


class FakeEntityStore:
    """记录 Milvus 实体集合调用。"""

    def __init__(self, *, search_hits=None) -> None:
        self.search_hits = search_hits or []
        self.deletes = []
        self.upserts = []

    async def search_entities(self, *, collection_name, vector, limit):
        """返回命中一次，之后模拟集合为空。"""
        hits = list(self.search_hits)
        self.search_hits = []
        return hits

    async def delete(self, *, collection_name, ids=None, record_ids=None, filter=None):
        """记录按过滤条件删除。"""
        self.deletes.append((collection_name, filter))
        return {"delete_count": 1}

    async def upsert_entities(self, *, collection_name, dimension, rows):
        """记录实体向量写入。"""
        self.upserts.append((collection_name, dimension, rows))
        return {"upsert_count": len(rows)}


class FakeGraphStore:
    """记录 Neo4j 写入与清理调用。"""

    def __init__(self) -> None:
        self.entity_writes = []
        self.relation_writes = []
        self.file_deletes = []

    async def upsert_entities(self, *, kb_id, file_id, entities):
        """记录实体写入。"""
        self.entity_writes.append((kb_id, file_id, entities))

    async def create_relations(self, *, kb_id, file_id, relations):
        """记录关系写入。"""
        self.relation_writes.append((kb_id, file_id, relations))

    async def delete_by_file(self, *, kb_id, file_id):
        """记录按文件清理。"""
        self.file_deletes.append((kb_id, file_id))


def _build_result() -> GraphExtractionResult:
    """构造两实体一关系的固定抽取结果。"""
    from src.knowledge.graph import GraphEntity, GraphRelation

    return GraphExtractionResult(
        entities=[
            GraphEntity(name="OpenAI", type="组织", description="AI 公司"),
            GraphEntity(name="GPT", type="产品", description="大语言模型"),
        ],
        relations=[GraphRelation(source="OpenAI", target="GPT", type="发布")],
    )


class KnowledgeExtractServiceTest(unittest.IsolatedAsyncioTestCase):
    def _patch_context(
        self,
        *,
        extractor,
        entity_store,
        graph_store,
        files,
    ):
        """组装抽取流程所需的全量依赖补丁。"""
        stack = ExitStack()
        for target, fake in (
            ("KnowledgeFileRepository", files),
            ("KnowledgeEmbeddingBindingRepository", FakeBindingRepository()),
            ("get_storage", FakeStorage()),
            ("GraphExtractor", extractor),
            ("_get_knowledge", entity_store),
            ("get_graph_store", graph_store),
            ("_create_embedding_service", (FakeEmbeddingService(), "mock/model", 2)),
        ):
            stack.enter_context(
                patch.object(knowledge_service, target, return_value=fake)
            )
        return stack

    async def test_extract_writes_entities_relations_and_vectors(self) -> None:
        """抽取成功写入 Neo4j 与 Milvus 并更新状态。"""
        session = FakeSession()
        files = FakeKnowledgeFileRepository()
        entity_store = FakeEntityStore()
        graph_store = FakeGraphStore()
        with self._patch_context(
            extractor=FakeExtractor(result=_build_result()),
            entity_store=entity_store,
            graph_store=graph_store,
            files=files,
        ):
            result = await knowledge_service.extract_file(
                session,
                uid="user-1",
                kb_id="kb-1",
                file_id="file-1",
            )

        self.assertEqual("extracted", files.file.status)
        self.assertEqual(2, result["entity_count"])
        self.assertEqual(1, result["relation_count"])
        self.assertEqual(1, len(graph_store.entity_writes))
        self.assertEqual(2, len(graph_store.entity_writes[0][2]))
        self.assertEqual(1, len(graph_store.relation_writes))
        self.assertEqual(2, len(entity_store.upserts[0][2]))
        self.assertEqual(2, session.commits)

    async def test_extract_rejects_non_indexed_file(self) -> None:
        """只有 indexed/extracted 状态的文件可以抽取。"""
        files = FakeKnowledgeFileRepository(status="parsed")
        with self._patch_context(
            extractor=FakeExtractor(),
            entity_store=FakeEntityStore(),
            graph_store=FakeGraphStore(),
            files=files,
        ):
            with self.assertRaisesRegex(ValueError, "不允许抽取"):
                await knowledge_service.extract_file(
                    FakeSession(),
                    uid="user-1",
                    kb_id="kb-1",
                    file_id="file-1",
                )

    async def test_extract_failure_reverts_to_indexed(self) -> None:
        """抽取失败回退 indexed 并记录错误信息。"""
        session = FakeSession()
        files = FakeKnowledgeFileRepository()
        with self._patch_context(
            extractor=FakeExtractor(error=RuntimeError("llm down")),
            entity_store=FakeEntityStore(),
            graph_store=FakeGraphStore(),
            files=files,
        ):
            with self.assertRaises(RuntimeError):
                await knowledge_service.extract_file(
                    session,
                    uid="user-1",
                    kb_id="kb-1",
                    file_id="file-1",
                )

        self.assertEqual("indexed", files.file.status)
        self.assertIn("llm down", files.file.error_message)
        self.assertEqual(1, session.rollbacks)

    async def test_re_extract_cleans_previous_graph_data(self) -> None:
        """重抽取前清理该文件旧实体与向量。"""
        files = FakeKnowledgeFileRepository(status="extracted")
        entity_store = FakeEntityStore()
        graph_store = FakeGraphStore()
        with self._patch_context(
            extractor=FakeExtractor(result=_build_result()),
            entity_store=entity_store,
            graph_store=graph_store,
            files=files,
        ):
            await knowledge_service.extract_file(
                FakeSession(),
                uid="user-1",
                kb_id="kb-1",
                file_id="file-1",
            )

        expected_collection = knowledge_service._entity_collection_name(
            "user-1", "kb-1"
        )
        self.assertEqual(
            [(expected_collection, 'file_id == "file-1"')],
            entity_store.deletes,
        )
        self.assertEqual([("kb-1", "file-1")], graph_store.file_deletes)

    async def test_similar_entity_merges_into_existing(self) -> None:
        """相似实体合并到已有实体，不新建节点。"""
        entity_store = FakeEntityStore(
            search_hits=[
                {
                    "id": "existing-1",
                    "distance": 0.95,
                    "entity": {
                        "name": "OpenAI",
                        "entity_type": "组织",
                        "description": "",
                        "file_id": "file-0",
                    },
                },
                {"id": "existing-2", "distance": 0.3, "entity": {}},
            ]
        )
        graph_store = FakeGraphStore()
        with self._patch_context(
            extractor=FakeExtractor(result=_build_result()),
            entity_store=entity_store,
            graph_store=graph_store,
            files=FakeKnowledgeFileRepository(),
        ):
            result = await knowledge_service.extract_file(
                FakeSession(),
                uid="user-1",
                kb_id="kb-1",
                file_id="file-1",
            )

        self.assertEqual(2, result["entity_count"])
        self.assertEqual(1, len(entity_store.upserts[0][2]))
        source_id = graph_store.relation_writes[0][2][0]["source_entity_id"]
        self.assertEqual("existing-1", source_id)


if __name__ == "__main__":
    unittest.main()
