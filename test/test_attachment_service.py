"""附件临时上传 UUID 契约测试。"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

from server.service import attachment_service


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class FakeStorage:
    def __init__(self) -> None:
        self.upload_calls = []
        self.delete_calls = []

    async def aupload_file(
        self,
        bucket_name,
        object_name,
        content_data,
        content_type=None,
    ):
        self.upload_calls.append(
            (bucket_name, object_name, content_data, content_type)
        )

    async def create_file_access_url(self, bucket_name, object_name):
        return f"https://files/{bucket_name}/{object_name}"

    async def adelete_file(self, bucket_name, object_name):
        self.delete_calls.append((bucket_name, object_name))
        return True


class FakeAttachmentRepository:
    def __init__(self) -> None:
        self.next_id = 1
        self.rows = []
        self.error = None

    async def create_pending_attachment(self, **values):
        if self.error is not None:
            raise self.error
        attachment = SimpleNamespace(
            id=self.next_id,
            status="pending",
            **values,
        )
        self.next_id += 1
        self.rows.append(attachment)
        return attachment


class AttachmentUploadTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.db = FakeSession()
        self.storage = FakeStorage()
        self.repository = FakeAttachmentRepository()
        self.repository_patch = patch(
            "server.service.attachment_service.AttachmentRepository",
            return_value=self.repository,
        )
        self.storage_patch = patch(
            "server.service.attachment_service.get_storage",
            return_value=self.storage,
        )
        self.repository_patch.start()
        self.storage_patch.start()
        self.addCleanup(self.repository_patch.stop)
        self.addCleanup(self.storage_patch.stop)

    async def test_upload_reuses_uuid_for_path_record_and_response(self):
        result = await attachment_service.upload_pending_attachments(
            self.db,
            user_id=7,
            uploads=[
                attachment_service.PendingAttachmentUpload(
                    file_name="requirements.pdf",
                    content_type="application/pdf",
                    content=b"pdf",
                    category="document",
                )
            ],
        )

        response = result[0]
        file_id = response["id"]
        self.assertEqual(4, UUID(file_id).version)
        self.assertEqual(file_id, self.repository.rows[0].file_id)
        expected_object_name = (
            f"tmp/7/chat/attachment/{file_id}/requirements.pdf"
        )
        self.assertEqual(
            expected_object_name,
            self.repository.rows[0].original_object_name,
        )
        self.assertEqual(
            "attachment",
            self.storage.upload_calls[0][0],
        )
        self.assertEqual(
            expected_object_name,
            self.storage.upload_calls[0][1],
        )
        self.assertEqual(1, self.db.commits)
        self.assertEqual(0, self.db.rollbacks)

    async def test_database_failure_removes_uploaded_temporary_object(self):
        self.repository.error = RuntimeError("database failed")

        with patch.object(attachment_service.logger, "exception"):
            with self.assertRaisesRegex(RuntimeError, "database failed"):
                await attachment_service.upload_pending_attachments(
                    self.db,
                    user_id=7,
                    uploads=[
                        attachment_service.PendingAttachmentUpload(
                            file_name="需求.pdf",
                            content_type="application/pdf",
                            content=b"pdf",
                            category="document",
                        )
                    ],
                )

        self.assertEqual(1, self.db.rollbacks)
        self.assertEqual(
            [("attachment", self.storage.upload_calls[0][1])],
            self.storage.delete_calls,
        )


if __name__ == "__main__":
    unittest.main()
