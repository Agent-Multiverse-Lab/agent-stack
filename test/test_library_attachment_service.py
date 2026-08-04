"""用户附件 Library Repository 与函数式用例测试。"""

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.dialects import postgresql

from server.router.library_router import router
from server.service import library_service
from src.database.repositories import AttachmentRepository

NOW = datetime(2026, 8, 4, 10, 0, tzinfo=UTC)
FILE_ID_1 = "759b114e-90d6-42d2-a052-bdccaa40c7b6"
FILE_ID_2 = "123e4567-e89b-42d3-a456-426614174000"


class ScalarRows:
    def all(self):
        return []


class EmptyResult:
    def scalars(self):
        return ScalarRows()


class CaptureSession:
    def __init__(self) -> None:
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return EmptyResult()

    async def flush(self):
        return None


class FakeStorage:
    def __init__(self) -> None:
        self.access_calls = []

    async def create_file_access_url(self, bucket_name, object_name):
        self.access_calls.append((bucket_name, object_name))
        return f"https://files/{object_name}"


class FakeAttachmentRepository:
    def __init__(self) -> None:
        self.rows = []
        self.attachment = None
        self.list_arguments = None
        self.get_arguments = None
        self.renamed_to = None
        self.deleted_attachment = None

    async def list_library_attachments_for_user(self, **values):
        self.list_arguments = values
        return self.rows[: values["limit"]]

    async def get_library_attachment_by_file_id_for_user(self, **values):
        self.get_arguments = values
        return self.attachment

    async def update_attachment_name(
        self,
        attachment,
        *,
        attachment_name,
    ):
        self.renamed_to = attachment_name
        attachment.attachment_name = attachment_name
        attachment.updated_at = NOW
        return attachment

    async def soft_delete_attachment(self, attachment):
        self.deleted_attachment = attachment
        attachment.deleted_at = NOW
        attachment.updated_at = NOW


def make_attachment(
    attachment_id: int,
    *,
    file_name: str = "需求.PDF",
    status: str = "parsed",
    error_message: str | None = None,
) -> SimpleNamespace:
    file_id = FILE_ID_1 if attachment_id == 3 else FILE_ID_2
    return SimpleNamespace(
        id=attachment_id,
        file_id=file_id,
        user_id=7,
        attachment_name=file_name,
        attachment_type="application/pdf",
        attachment_size=1024,
        original_object_name=f"7/{file_id}/original/{file_name}",
        markdown_object_name=f"7/{file_id}/parsed/document.md",
        status=status,
        error_message=error_message,
        deleted_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


class AttachmentRepositoryTest(unittest.IsolatedAsyncioTestCase):
    async def test_library_query_excludes_pending_and_deleted_rows(self):
        session = CaptureSession()
        await AttachmentRepository(
            session
        ).list_library_attachments_for_user(
            user_id=7,
            limit=20,
            before_id=120,
            query="需求",
        )

        sql = str(
            session.statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        self.assertIn("attachment.user_id = 7", sql)
        self.assertIn("attachment.deleted_at IS NULL", sql)
        self.assertIn("attachment.status IN", sql)
        for attachment_status in ("failed", "parsed", "parsing", "uploaded"):
            self.assertIn(f"'{attachment_status}'", sql)
        self.assertNotIn("'pending'", sql)
        self.assertIn("attachment.id < 120", sql)
        self.assertIn("ORDER BY attachment.id DESC", sql)

    async def test_soft_delete_sets_one_shared_timestamp(self):
        session = CaptureSession()
        attachment = make_attachment(3)

        await AttachmentRepository(session).soft_delete_attachment(
            attachment
        )

        self.assertIsNotNone(attachment.deleted_at)
        self.assertEqual(attachment.deleted_at, attachment.updated_at)


class LibraryAttachmentUseCaseTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = FakeAttachmentRepository()
        self.storage = FakeStorage()
        self.repository_patch = patch(
            "server.service.library_service.AttachmentRepository",
            return_value=self.repository,
        )
        self.storage_patch = patch(
            "server.service.library_service.get_storage",
            return_value=self.storage,
        )
        self.repository_patch.start()
        self.storage_patch.start()
        self.addCleanup(self.repository_patch.stop)
        self.addCleanup(self.storage_patch.stop)

    async def test_list_returns_cursor_without_thread_id(self):
        first = make_attachment(3, error_message="解析失败")
        self.repository.rows = [first, make_attachment(2)]

        result = await library_service.list_library_attachments(
            SimpleNamespace(),
            user_id=7,
            limit=1,
            query=" 需求 ",
        )

        item = result["items"][0]
        self.assertEqual(3, result["next_before_id"])
        self.assertEqual(".pdf", item["suffix"])
        self.assertEqual(str(FILE_ID_1), item["id"])
        self.assertEqual("解析失败", item["parse_error"])
        self.assertNotIn("thread_id", item)
        self.assertNotIn("original_object_name", item)
        self.assertEqual(
            [("attachment", first.original_object_name)],
            self.storage.access_calls,
        )
        self.assertEqual("需求", self.repository.list_arguments["query"])

    async def test_get_hides_pending_or_missing_record(self):
        with self.assertRaisesRegex(LookupError, "不存在或已删除"):
            await library_service.get_library_attachment(
                SimpleNamespace(),
                user_id=7,
                attachment_id=str(FILE_ID_1),
            )

    async def test_rename_keeps_original_object_name(self):
        attachment = make_attachment(3)
        self.repository.attachment = attachment
        original_object_name = attachment.original_object_name

        result = await library_service.rename_library_attachment(
            SimpleNamespace(),
            user_id=7,
            attachment_id=str(FILE_ID_1),
            file_name="新需求.pdf",
        )

        self.assertEqual("新需求.pdf", result["file_name"])
        self.assertEqual("新需求.pdf", self.repository.renamed_to)
        self.assertEqual(FILE_ID_1, self.repository.get_arguments["file_id"])
        self.assertEqual(
            original_object_name,
            attachment.original_object_name,
        )

    async def test_rename_rejects_path_and_suffix_change(self):
        self.repository.attachment = make_attachment(3)
        with self.assertRaises(ValueError):
            await library_service.rename_library_attachment(
                SimpleNamespace(),
                user_id=7,
                attachment_id=str(FILE_ID_1),
                file_name="folder/new.pdf",
            )
        with self.assertRaises(ValueError):
            await library_service.rename_library_attachment(
                SimpleNamespace(),
                user_id=7,
                attachment_id=str(FILE_ID_1),
                file_name="new.docx",
            )

    async def test_delete_uses_soft_delete(self):
        attachment = make_attachment(3)
        self.repository.attachment = attachment

        await library_service.delete_library_attachment(
            SimpleNamespace(),
            user_id=7,
            attachment_id=str(FILE_ID_1),
        )

        self.assertIs(attachment, self.repository.deleted_attachment)
        self.assertEqual(NOW, attachment.deleted_at)

    def test_router_exposes_attachment_crud(self):
        methods_by_path: dict[str, set[str]] = {}
        for route in router.routes:
            if hasattr(route, "methods"):
                methods_by_path.setdefault(route.path, set()).update(
                    route.methods
                )

        self.assertIn("GET", methods_by_path["/libraries/attachments"])
        self.assertEqual(
            {"GET", "PATCH", "DELETE"},
            methods_by_path["/libraries/attachments/{attachment_id}"],
        )


if __name__ == "__main__":
    unittest.main()
