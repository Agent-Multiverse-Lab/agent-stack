"""知识库 Embedding 持久绑定测试。"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.embeddings import Embeddings

from server.service import knowledge_service
from src.configs import config as sys_config


class FakeEmbeddings(Embeddings):
    """返回固定三维向量。"""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """同步生成文档向量。"""
        return [[1.0, 2.0, 3.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        """同步生成查询向量。"""
        return [1.0, 2.0, 3.0]


class FakeSession:
    """记录服务提交行为。"""

    def __init__(self) -> None:
        self.new = {object()}
        self.commits = 0

    async def commit(self) -> None:
        """记录一次提交。"""
        self.commits += 1


class FakeBindingRepository:
    """在内存中模拟唯一知识库绑定。"""

    def __init__(self, session: FakeSession) -> None:
        self.binding = None

    async def get(self, *, uid: str, kb_id: str):
        """返回当前绑定。"""
        return self.binding

    async def create(self, **values):
        """保存首次绑定。"""
        self.binding = SimpleNamespace(**values)
        return self.binding


class FakeKnowledge:
    """记录 Milvus 层收到的查询向量。"""

    def __init__(self) -> None:
        self.search_vector = None

    async def search(self, *, collection_name, vector, limit):
        """记录查询向量。"""
        self.search_vector = vector
        return [{"id": "1"}]


class KnowledgeEmbeddingBindingTest(unittest.IsolatedAsyncioTestCase):
    async def test_search_uses_persisted_model_contract(self) -> None:
        session = FakeSession()
        knowledge = FakeKnowledge()
        provider = SimpleNamespace(batch_size=99)
        binding = SimpleNamespace(
            uid="user-1",
            kb_id="kb-1",
            collection_name="kb_collection",
            embedding_model_spec="mock/bound",
            embedding_dimension=3,
            embedding_batch_size=2,
        )
        bindings = FakeBindingRepository(session)
        bindings.binding = binding

        with (
            patch(
                "server.service.knowledge_service.KnowledgeFactory.create",
                return_value=knowledge,
            ),
            patch(
                "server.service.knowledge_service.MilvusKnowledge",
                FakeKnowledge,
            ),
            patch(
                "server.service.knowledge_service."
                "KnowledgeEmbeddingBindingRepository",
                return_value=bindings,
            ),
            patch(
                "server.service.knowledge_service.resolve_embedding_model",
                return_value=("mock/bound", "bound", provider),
            ) as resolve_model,
            patch(
                "server.service.knowledge_service.load_embedding_model",
                return_value=FakeEmbeddings(),
            ),
            patch.object(sys_config, "rerank_model", ""),
        ):
            result = await knowledge_service.search(
                session,
                uid="user-1",
                kb_id="kb-1",
                query="query",
                limit=5,
                knowledge_type="milvus",
            )

        resolve_model.assert_called_once_with("mock/bound")
        self.assertEqual([1.0, 2.0, 3.0], knowledge.search_vector)
        self.assertEqual("mock/bound", result["embedding_model_spec"])
        self.assertEqual(3, result["embedding_dimension"])


if __name__ == "__main__":
    unittest.main()
