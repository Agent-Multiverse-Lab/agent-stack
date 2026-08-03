"""知识文件解析阶段契约测试。"""

import unittest
from types import SimpleNamespace

from server.service.knowledge_service import KnowledgeService
from src.knowledge.flow import ParsedDocument


class FakeSession:
    """记录事务边界。"""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        """记录提交。"""
        self.commits += 1

    async def rollback(self) -> None:
        """记录回滚。"""
        self.rollbacks += 1


class FakeKnowledgeBaseRepository:
    """返回固定知识库。"""

    def __init__(self, *, exists=True) -> None:
        self.exists = exists

    async def get_for_user(self, **kwargs):
        """返回用户拥有的知识库。"""
        if not self.exists:
            return None
        return SimpleNamespace(kb_id=kwargs["kb_id"])


class FakeKnowledgeFileRepository:
    """在内存中维护知识文件状态。"""

    def __init__(self, knowledge_file=None, *, file_names=None) -> None:
        self.knowledge_file = knowledge_file
        self.file_names = file_names or []

    async def create(self, **values):
        """创建上传文件记录。"""
        self.knowledge_file = SimpleNamespace(
            **values,
            markdown_object_name=None,
            status="uploaded",
            error_message=None,
        )
        return self.knowledge_file

    async def get_for_user(self, **kwargs):
        """返回当前文件。"""
        return self.knowledge_file

    async def list_names_for_user(self, **kwargs):
        """返回当前知识库中的文件名。"""
        return self.file_names

    async def update_status(
        self,
        knowledge_file,
        *,
        status,
        markdown_object_name=None,
        error_message=None,
    ):
        """更新内存文件状态。"""
        knowledge_file.status = status
        knowledge_file.error_message = error_message
        if markdown_object_name is not None:
            knowledge_file.markdown_object_name = markdown_object_name
        return knowledge_file


class FakeStorage:
    """记录 MinIO 下载和上传。"""

    def __init__(self) -> None:
        self.uploads = []

    async def aupload_file(
        self,
        bucket_name,
        object_name,
        content_data,
        content_type=None,
    ):
        """记录上传内容。"""
        self.uploads.append(
            (bucket_name, object_name, content_data, content_type)
        )

    async def adownload_file(self, bucket_name, object_name):
        """返回固定原文件。"""
        return b"source"

    async def adelete_file(self, bucket_name, object_name):
        """模拟删除原文件。"""
        return True


class FakePipeline:
    """只执行解析，不暴露分块入口。"""

    async def parse_document(self, content, *, file_name):
        """返回固定 Markdown。"""
        return ParsedDocument(
            name=file_name,
            suffix=".txt",
            markdown="# Parsed\n\ncontent",
        )


class KnowledgeParseServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_list_file_names_for_current_knowledge_base(self) -> None:
        """只返回当前用户指定知识库中的原始文件名。"""
        service = KnowledgeService(
            FakeSession(),
            storage=FakeStorage(),
            pipeline=FakePipeline(),
        )
        service.knowledge_bases = FakeKnowledgeBaseRepository()
        service.knowledge_files = FakeKnowledgeFileRepository(
            file_names=["接口说明.md", "产品需求.pdf"]
        )

        result = await service.list_file_names(
            uid="user-1",
            kb_id="kb-1",
        )

        self.assertEqual(["接口说明.md", "产品需求.pdf"], result)

    async def test_list_file_names_rejects_unknown_knowledge_base(self) -> None:
        """不存在或不属于当前用户的知识库不能读取文件列表。"""
        service = KnowledgeService(
            FakeSession(),
            storage=FakeStorage(),
            pipeline=FakePipeline(),
        )
        service.knowledge_bases = FakeKnowledgeBaseRepository(exists=False)
        service.knowledge_files = FakeKnowledgeFileRepository()

        with self.assertRaisesRegex(LookupError, "知识库不存在"):
            await service.list_file_names(uid="user-1", kb_id="kb-1")

    async def test_upload_creates_knowledge_file_without_parsing(self) -> None:
        session = FakeSession()
        storage = FakeStorage()
        service = KnowledgeService(
            session,
            storage=storage,
            pipeline=FakePipeline(),
        )
        service.knowledge_bases = FakeKnowledgeBaseRepository()
        service.knowledge_files = FakeKnowledgeFileRepository()

        knowledge_file = await service.upload_file(
            uid="user-1",
            kb_id="kb-1",
            file_name="guide.txt",
            content=b"content",
            content_type="text/plain",
        )

        self.assertEqual("uploaded", knowledge_file.status)
        self.assertIsNone(knowledge_file.markdown_object_name)
        self.assertIn("/original/guide.txt", knowledge_file.original_object_name)
        self.assertEqual(1, session.commits)

    async def test_parse_file_saves_markdown_without_chunking(self) -> None:
        session = FakeSession()
        storage = FakeStorage()
        knowledge_file = SimpleNamespace(
            file_id="file-1",
            kb_id="kb-1",
            original_file_name="guide.txt",
            original_object_name="original/guide.txt",
            markdown_object_name=None,
            content_type="text/plain",
            file_size=6,
            status="uploaded",
            error_message=None,
        )
        service = KnowledgeService(
            session,
            storage=storage,
            pipeline=FakePipeline(),
        )
        service.knowledge_files = FakeKnowledgeFileRepository(knowledge_file)

        result = await service.parse_file(
            uid="user-1",
            kb_id="kb-1",
            file_id="file-1",
        )

        self.assertEqual("parsed", result.status)
        self.assertTrue(result.markdown_object_name.endswith("/document.md"))
        self.assertEqual(b"# Parsed\n\ncontent", storage.uploads[0][2])
        self.assertEqual(2, session.commits)
