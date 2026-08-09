"""附件临时上传 UUID 契约测试。"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

from server.service import attachment_service
from src.database.repositories import MessageAttachmentRepository


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
        self.copy_calls = []
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

    async def acopy_file(
        self,
        bucket_name,
        source_object_name,
        target_object_name,
    ):
        self.copy_calls.append(
            (bucket_name, source_object_name, target_object_name)
        )

    async def adelete_file(self, bucket_name, object_name):
        self.delete_calls.append((bucket_name, object_name))
        return True


class FakeAttachmentRepository:
    def __init__(self) -> None:
        self.next_id = 1
        self.rows = []
        self.error = None
        self.update_error = None

    async def create_attachment(self, **values):
        if self.error is not None:
            raise self.error
        attachment = SimpleNamespace(
            id=self.next_id,
            **values,
        )
        self.next_id += 1
        self.rows.append(attachment)
        return attachment

    async def list_by_file_ids_for_user(self, **values):
        return [
            row
            for row in self.rows
            if row.file_id in values["file_ids"]
            and row.user_id == int(values["user_id"])
        ]

    async def update_object_name(self, attachment, *, object_name):
        if self.update_error is not None:
            raise self.update_error
        attachment.object_name = object_name


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
        result = await attachment_service.upload_attachments(
            self.db,
            user_id=7,
            uploads=[
                attachment_service.AttachmentUpload(
                    file_name="requirements.pdf",
                    content_type="application/pdf",
                    content=b"pdf",
                )
            ],
        )

        response = result[0]
        file_id = response["file_id"]
        self.assertEqual(4, UUID(file_id).version)
        self.assertEqual(file_id, self.repository.rows[0].file_id)
        expected_object_name = f"save/attachments/{file_id}"
        self.assertEqual(
            expected_object_name,
            self.repository.rows[0].object_name,
        )
        self.assertEqual(
            "attachment",
            self.storage.upload_calls[0][0],
        )
        self.assertEqual(
            expected_object_name,
            self.storage.upload_calls[0][1],
        )
        self.assertEqual("attachment", response["bucket_name"])
        self.assertEqual(expected_object_name, response["object_name"])
        self.assertEqual(1, self.db.commits)
        self.assertEqual(0, self.db.rollbacks)

    async def test_database_failure_removes_uploaded_temporary_object(self):
        self.repository.error = RuntimeError("database failed")

        with patch.object(attachment_service.logger, "exception"):
            with self.assertRaisesRegex(RuntimeError, "database failed"):
                await attachment_service.upload_attachments(
                    self.db,
                    user_id=7,
                    uploads=[
                        attachment_service.AttachmentUpload(
                            file_name="需求.pdf",
                            content_type="application/pdf",
                            content=b"pdf",
                        )
                    ],
                )

        self.assertEqual(1, self.db.rollbacks)
        self.assertEqual(
            [("attachment", self.storage.upload_calls[0][1])],
            self.storage.delete_calls,
        )

    async def test_prepare_moves_uploaded_object_to_thread_path(self):
        attachment = SimpleNamespace(
            id=1,
            file_id="759b114e-90d6-42d2-a052-bdccaa40c7b6",
            user_id=7,
            object_name=(
                "save/attachments/759b114e-90d6-42d2-a052-bdccaa40c7b6"
            ),
        )
        self.repository.rows = [attachment]

        rows, copied = await attachment_service.prepare_message_attachments(
            self.db,
            user_id=7,
            thread_id="thread-1",
            file_ids=[attachment.file_id],
        )

        target = (
            "save/thread-1/attachments/"
            "759b114e-90d6-42d2-a052-bdccaa40c7b6"
        )
        self.assertEqual([attachment], rows)
        self.assertEqual(
            [("attachment", copied[0][0], target)],
            self.storage.copy_calls,
        )
        self.assertEqual(target, attachment.object_name)

    async def test_prepare_rejects_missing_or_other_user_attachment(self):
        attachment = SimpleNamespace(
            id=1,
            file_id="759b114e-90d6-42d2-a052-bdccaa40c7b6",
            user_id=8,
            object_name=(
                "save/attachments/759b114e-90d6-42d2-a052-bdccaa40c7b6"
            ),
        )
        self.repository.rows = [attachment]

        with self.assertRaisesRegex(LookupError, "不属于当前用户"):
            await attachment_service.prepare_message_attachments(
                self.db,
                user_id=7,
                thread_id="thread-1",
                file_ids=[attachment.file_id],
            )

        self.assertEqual([], self.storage.copy_calls)

    async def test_prepare_failure_removes_copied_target(self):
        attachment = SimpleNamespace(
            id=1,
            file_id="759b114e-90d6-42d2-a052-bdccaa40c7b6",
            user_id=7,
            object_name=(
                "save/attachments/759b114e-90d6-42d2-a052-bdccaa40c7b6"
            ),
        )
        self.repository.rows = [attachment]
        self.repository.update_error = RuntimeError("update failed")

        with self.assertRaisesRegex(RuntimeError, "update failed"):
            await attachment_service.prepare_message_attachments(
                self.db,
                user_id=7,
                thread_id="thread-1",
                file_ids=[attachment.file_id],
            )

        target = f"save/thread-1/attachments/{attachment.file_id}"
        self.assertEqual([("attachment", target)], self.storage.delete_calls)

    async def test_prepare_does_not_copy_moved_attachment_again(self):
        attachment = SimpleNamespace(
            id=1,
            file_id="759b114e-90d6-42d2-a052-bdccaa40c7b6",
            user_id=7,
            object_name=(
                "save/thread-1/attachments/"
                "759b114e-90d6-42d2-a052-bdccaa40c7b6"
            ),
        )
        self.repository.rows = [attachment]

        rows, copied = await attachment_service.prepare_message_attachments(
            self.db,
            user_id=7,
            thread_id="thread-2",
            file_ids=[attachment.file_id],
        )

        self.assertEqual([attachment], rows)
        self.assertEqual([], copied)
        self.assertEqual([], self.storage.copy_calls)

    def test_attachment_file_ids_are_uuid4_and_deduplicated(self):
        file_id = "759b114e-90d6-42d2-a052-bdccaa40c7b6"

        self.assertEqual(
            [file_id],
            attachment_service.attachment_file_ids(
                {"attachment_file_ids": [file_id, file_id]}
            ),
        )
        with self.assertRaisesRegex(ValueError, "UUID4"):
            attachment_service.attachment_file_ids(
                {"attachment_file_ids": ["invalid"]}
            )


class CaptureLinkSession:
    def __init__(self) -> None:
        self.rows = []
        self.flushes = 0

    def add_all(self, rows):
        self.rows.extend(rows)

    async def flush(self):
        self.flushes += 1


class MessageAttachmentRepositoryTest(unittest.IsolatedAsyncioTestCase):
    async def test_create_links_preserves_input_order(self):
        session = CaptureLinkSession()
        attachments = [
            SimpleNamespace(id=31),
            SimpleNamespace(id=29),
        ]

        await MessageAttachmentRepository(session).create_links(
            message_id=21,
            attachments=attachments,
        )

        self.assertEqual(
            [(21, 31, 0), (21, 29, 1)],
            [
                (row.message_id, row.attachment_id, row.position)
                for row in session.rows
            ],
        )
        self.assertEqual(1, session.flushes)


if __name__ == "__main__":
    unittest.main()
