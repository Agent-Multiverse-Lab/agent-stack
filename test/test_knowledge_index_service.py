"""知识文件确认式索引服务测试。"""

import unittest
from types import SimpleNamespace

from server.service.knowledge_service import KnowledgeService


class FakeSession:
    """记录索引流程的事务行为。"""

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

    def __init__(self) -> None:
        self.file = SimpleNamespace(
            file_id="file-1",
            kb_id="kb-1",
            original_file_name="manual.pdf",
            markdown_object_name="parsed/document.md",
            status="parsed",
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
    """返回已经解析并保存的 Markdown。"""

    async def adownload_file(self, bucket_name: str, object_name: str) -> bytes:
        """下载测试 Markdown。"""
        return b"# Title\n\nBody"


class FakePipeline:
    """模拟 Markdown 恢复和分块。"""

    async def parse_document(self, content: bytes, *, file_name: str):
        """恢复测试 ParsedDocument。"""
        return SimpleNamespace(markdown=content.decode())

    def chunk_document(self, document):
        """返回两个固定分块。"""
        return [
            SimpleNamespace(text="Title", metadata={"title_path": ["Title"]}),
            SimpleNamespace(text="Body", metadata={"title_path": ["Title"]}),
        ]


class FakeEmbeddingService:
    """返回固定维度的分块向量。"""

    dimension = 3

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """为每个测试分块生成三维向量。"""
        return [[1.0, 2.0, 3.0] for _ in texts]


class FakeBindingRepository:
    """保存首次索引创建的 Embedding 绑定。"""

    def __init__(self) -> None:
        self.binding = None

    async def get(self, *, uid: str, kb_id: str):
        """返回当前测试绑定。"""
        return self.binding

    async def create(self, **values):
        """创建并返回测试绑定。"""
        self.binding = SimpleNamespace(**values)
        return self.binding


class FakeKnowledge:
    """记录 Milvus 文件索引入口收到的数据。"""

    def __init__(self) -> None:
        self.file_id = None
        self.records = []

    async def build_file_index(
        self,
        *,
        collection_name,
        file_id,
        dimension,
        records,
    ):
        """记录已向量化的文件分块。"""
        self.file_id = file_id
        self.records = records
        return {"upsert_count": len(records)}


class KnowledgeIndexServiceTest(unittest.IsolatedAsyncioTestCase):
    """验证用户确认后才执行索引。"""

    async def test_index_file_chunks_and_upserts_parsed_markdown(self) -> None:
        """索引成功后写入稳定分块 ID 并更新文件状态。"""
        session = FakeSession()
        service = KnowledgeService(
            session,
            storage=FakeStorage(),
            pipeline=FakePipeline(),
        )
        service.knowledge_files = FakeKnowledgeFileRepository()
        service.bindings = FakeBindingRepository()
        knowledge = FakeKnowledge()
        service._knowledge = knowledge
        service._create_embedding_service = lambda *args, **kwargs: (
            FakeEmbeddingService(),
            "mock/model",
            2,
        )

        result = await service.index_file(
            uid="user-1",
            kb_id="kb-1",
            file_id="file-1",
        )

        self.assertEqual(
            ["file-1:0", "file-1:1"],
            [item.id for item in knowledge.records],
        )
        self.assertEqual("file-1", knowledge.file_id)
        self.assertEqual(
            "file-1",
            knowledge.records[0].metadata["file_id"],
        )
        self.assertEqual("indexed", service.knowledge_files.file.status)
        self.assertEqual(2, result["chunk_count"])
        self.assertEqual(3, session.commits)


if __name__ == "__main__":
    unittest.main()
