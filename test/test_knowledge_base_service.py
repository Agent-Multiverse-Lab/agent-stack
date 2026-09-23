"""知识库生命周期服务测试。"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from server.service import knowledge_service


class FakeSession:
    """记录事务边界与删除动作。"""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.deleted = []

    async def commit(self) -> None:
        """记录提交。"""
        self.commits += 1

    async def rollback(self) -> None:
        """记录回滚。"""
        self.rollbacks += 1

    async def delete(self, obj) -> None:
        """记录待删除对象。"""
        self.deleted.append(obj)


class FakeKnowledgeBaseRepository:
    """返回固定知识库列表。"""

    def __init__(self, *, bases=None, exists=True) -> None:
        self.bases = bases or []
        self.exists = exists

    async def list_for_user(self, *, uid):
        """返回用户知识库。"""
        return self.bases

    async def get_for_user(self, *, uid, kb_id):
        """返回指定知识库。"""
        if not self.exists:
            return None
        return SimpleNamespace(kb_id=kb_id, name="docs", description="", status="active")


class FakeKnowledgeFileRepository:
    """返回固定文件列表。"""

    async def list_for_user(self, *, uid, kb_id):
        """返回两个测试文件。"""
        return [SimpleNamespace(file_id="f1"), SimpleNamespace(file_id="f2")]


class FakeBindingRepository:
    """返回固定 Embedding 绑定。"""

    def __init__(self, *, binding=None) -> None:
        self.binding = binding

    async def get(self, *, uid, kb_id):
        """返回测试绑定。"""
        return self.binding


class FakeKnowledge:
    """记录 Milvus 集合删除调用，可注入失败。"""

    def __init__(self, *, fail=False) -> None:
        self.dropped = []
        self.fail = fail

    async def drop_collection(self, *, collection_name):
        """记录集合删除。"""
        if self.fail:
            raise RuntimeError("milvus down")
        self.dropped.append(collection_name)
        return {"dropped": True, "exists": True}


class FakeGraphStore:
    """记录 Neo4j 清理调用。"""

    def __init__(self) -> None:
        self.deleted_kbs = []

    async def delete_by_kb(self, *, kb_id):
        """记录知识库图谱删除。"""
        self.deleted_kbs.append(kb_id)


class FakeStorage:
    """记录 RustFS 前缀删除调用。"""

    def __init__(self) -> None:
        self.deleted_prefixes = []

    async def adelete_objects_by_prefix(self, bucket_name, prefix):
        """记录前缀删除。"""
        self.deleted_prefixes.append((bucket_name, prefix))
        return 2


class KnowledgeBaseServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_list_returns_user_knowledge_bases(self) -> None:
        """列出当前用户全部知识库。"""
        bases = [SimpleNamespace(kb_id="kb-1"), SimpleNamespace(kb_id="kb-2")]
        with patch.object(
            knowledge_service,
            "KnowledgeBaseRepository",
            return_value=FakeKnowledgeBaseRepository(bases=bases),
        ):
            result = await knowledge_service.list_knowledge_bases(
                FakeSession(),
                uid="user-1",
            )

        self.assertEqual(["kb-1", "kb-2"], [item.kb_id for item in result])

    async def test_get_rejects_unknown_knowledge_base(self) -> None:
        """不存在或不属于当前用户的知识库不可读。"""
        with patch.object(
            knowledge_service,
            "KnowledgeBaseRepository",
            return_value=FakeKnowledgeBaseRepository(exists=False),
        ):
            with self.assertRaisesRegex(LookupError, "知识库不存在"):
                await knowledge_service.get_knowledge_base(
                    FakeSession(),
                    uid="user-1",
                    kb_id="kb-9",
                )

    async def test_delete_cleans_external_data_then_postgres(self) -> None:
        """删除知识库依次清理 Milvus、Neo4j、RustFS，最后删除 PG 行。"""
        session = FakeSession()
        binding = SimpleNamespace(
            kb_id="kb-1",
            collection_name="kb_collection",
            embedding_model_spec="mock/model",
            embedding_dimension=3,
            embedding_batch_size=8,
        )
        knowledge = FakeKnowledge()
        graph_store = FakeGraphStore()
        storage = FakeStorage()
        with (
            patch.object(
                knowledge_service,
                "KnowledgeBaseRepository",
                return_value=FakeKnowledgeBaseRepository(),
            ),
            patch.object(
                knowledge_service,
                "KnowledgeFileRepository",
                return_value=FakeKnowledgeFileRepository(),
            ),
            patch.object(
                knowledge_service,
                "KnowledgeEmbeddingBindingRepository",
                return_value=FakeBindingRepository(binding=binding),
            ),
            patch.object(
                knowledge_service,
                "_get_knowledge",
                return_value=knowledge,
            ),
            patch.object(
                knowledge_service,
                "get_graph_store",
                return_value=graph_store,
            ),
            patch.object(
                knowledge_service,
                "get_storage",
                return_value=storage,
            ),
        ):
            result = await knowledge_service.delete_knowledge_base(
                session,
                uid="user-1",
                kb_id="kb-1",
            )

        self.assertEqual(
            ["kb_collection", knowledge_service._entity_collection_name("user-1", "kb-1")],
            knowledge.dropped,
        )
        self.assertEqual(["kb-1"], graph_store.deleted_kbs)
        self.assertEqual(
            [("knowledgebases", "knowledge-files/user-1/kb-1/")],
            storage.deleted_prefixes,
        )
        self.assertEqual(1, len(session.deleted))
        self.assertEqual(1, session.commits)
        self.assertEqual(2, result["deleted_file_count"])

    async def test_delete_tolerates_external_failures(self) -> None:
        """外部存储清理失败不阻断 PostgreSQL 删除。"""
        session = FakeSession()
        binding = SimpleNamespace(
            kb_id="kb-1",
            collection_name="kb_collection",
            embedding_model_spec="mock/model",
            embedding_dimension=3,
            embedding_batch_size=8,
        )
        with (
            patch.object(
                knowledge_service,
                "KnowledgeBaseRepository",
                return_value=FakeKnowledgeBaseRepository(),
            ),
            patch.object(
                knowledge_service,
                "KnowledgeFileRepository",
                return_value=FakeKnowledgeFileRepository(),
            ),
            patch.object(
                knowledge_service,
                "KnowledgeEmbeddingBindingRepository",
                return_value=FakeBindingRepository(binding=binding),
            ),
            patch.object(
                knowledge_service,
                "_get_knowledge",
                return_value=FakeKnowledge(fail=True),
            ),
            patch.object(
                knowledge_service,
                "get_graph_store",
                return_value=FakeGraphStore(),
            ),
            patch.object(
                knowledge_service,
                "get_storage",
                return_value=FakeStorage(),
            ),
        ):
            result = await knowledge_service.delete_knowledge_base(
                session,
                uid="user-1",
                kb_id="kb-1",
            )

        self.assertEqual(1, len(session.deleted))
        self.assertEqual(1, session.commits)
        self.assertEqual(2, result["deleted_file_count"])


if __name__ == "__main__":
    unittest.main()
