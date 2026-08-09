"""Agent Run 创建事务与事件辅助函数测试。"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from server.entities.agent import AgentRunCreateRequest
from server.service import agent_run_service

FILE_ID_1 = "759b114e-90d6-42d2-a052-bdccaa40c7b6"
FILE_ID_2 = "123e4567-e89b-42d3-a456-426614174000"


class FakeSession:
    def __init__(self, events) -> None:
        self.events = events

    async def flush(self):
        self.events.append("flush")

    async def commit(self):
        self.events.append("commit")

    async def rollback(self):
        self.events.append("rollback")


class FakeConversationRepository:
    def __init__(self, events) -> None:
        self.events = events
        self.conversation = SimpleNamespace(id=9, agent_id="leaderagent")
        self.lookup_arguments = None
        self.message_arguments = None

    async def get_conversation_by_thread_id_for_user(self, **values):
        self.lookup_arguments = values
        return self.conversation

    async def create_agent_input_message(self, **values):
        self.events.append("message")
        self.message_arguments = values
        return SimpleNamespace(id=21, agent_run_id=None)


class FakeAgentRunRepository:
    def __init__(self, events) -> None:
        self.events = events
        self.arguments = None
        self.error = None
        self.run = None

    async def create_run(self, **values):
        self.events.append("run")
        if self.error is not None:
            raise self.error
        self.arguments = values
        self.run = SimpleNamespace(
            id=values["run_id"],
            thread_id=values["thread_id"],
            request_id=values["request_id"],
            agent_status="pending",
            error=None,
        )
        return self.run

    async def set_failed(self, run_id, error):
        self.events.append(("set_failed", run_id))
        self.run.agent_status = "failed"
        self.run.error = error
        return self.run


class FakeMessageAttachmentRepository:
    def __init__(self, events) -> None:
        self.events = events
        self.arguments = None

    async def create_links(self, **values):
        self.events.append("links")
        self.arguments = values


class AgentRunCreateTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.events = []
        self.db = FakeSession(self.events)
        self.conversations = FakeConversationRepository(self.events)
        self.runs = FakeAgentRunRepository(self.events)
        self.links = FakeMessageAttachmentRepository(self.events)
        self.attachments = [
            SimpleNamespace(id=31, file_id=FILE_ID_1),
            SimpleNamespace(id=32, file_id=FILE_ID_2),
        ]
        self.copied_objects = [
            (
                f"save/attachments/{FILE_ID_1}",
                f"save/thread-1/attachments/{FILE_ID_1}",
            )
        ]

        async def prepare_message_attachments(_db, **values):
            self.events.append("prepare")
            self.prepare_arguments = values
            file_ids = values["file_ids"]
            attachments = [
                attachment
                for attachment in self.attachments
                if attachment.file_id in file_ids
            ]
            return attachments, self.copied_objects if attachments else []

        async def delete_copied_sources(copied_objects):
            self.events.append(("delete_sources", copied_objects))

        async def delete_copied_targets(copied_objects):
            self.events.append(("delete_targets", copied_objects))

        patches = (
            patch(
                "server.service.agent_run_service.ConversationRepository",
                return_value=self.conversations,
            ),
            patch(
                "server.service.agent_run_service.AgentRunRepository",
                return_value=self.runs,
            ),
            patch(
                "server.service.agent_run_service.MessageAttachmentRepository",
                return_value=self.links,
            ),
            patch(
                "server.service.agent_run_service.prepare_message_attachments",
                side_effect=prepare_message_attachments,
            ),
            patch(
                "server.service.agent_run_service.delete_copied_sources",
                side_effect=delete_copied_sources,
            ),
            patch(
                "server.service.agent_run_service.delete_copied_targets",
                side_effect=delete_copied_targets,
            ),
        )
        for current_patch in patches:
            current_patch.start()
            self.addCleanup(current_patch.stop)

    async def create_run(self, **overrides):
        values = {
            "db": self.db,
            "current_user": SimpleNamespace(id=7, uid="user-1"),
            "query": "分析附件",
            "agent_id": "leaderagent",
            "thread_id": "thread-1",
            "thread_metadata": {"request_id": "request-1"},
            "msg_metadata": {
                "attachment_file_ids": [str(FILE_ID_1), str(FILE_ID_2)],
                "source": "web",
            },
            "image_content": None,
            "parent_run_id": None,
        }
        values.update(overrides)
        return await agent_run_service.create_agent_run_service(**values)

    async def test_create_commits_message_and_run_before_enqueue(self):
        async def enqueue(run_id):
            self.events.append(("enqueue", run_id))

        with patch(
            "server.service.agent_run_service.enqueue_agent_run",
            side_effect=enqueue,
        ):
            run = await self.create_run()

        self.assertEqual(
            {
                "attachment_file_ids": [str(FILE_ID_1), str(FILE_ID_2)],
                "source": "web",
            },
            self.conversations.message_arguments["msg_metadata"],
        )
        self.assertEqual(
            "multimodal",
            self.conversations.message_arguments["message_type"],
        )
        self.assertEqual(21, self.runs.arguments["trigger_message_id"])
        self.assertEqual(
            [
                "prepare",
                "message",
                "links",
                "run",
                "flush",
                "commit",
                ("delete_sources", self.copied_objects),
                ("enqueue", str(run.id)),
            ],
            self.events,
        )

    async def test_transaction_error_rolls_back_without_enqueue(self):
        self.runs.error = RuntimeError("run failed")

        with patch(
            "server.service.agent_run_service.enqueue_agent_run"
        ) as enqueue:
            with self.assertRaisesRegex(RuntimeError, "run failed"):
                await self.create_run()

        enqueue.assert_not_called()
        self.assertEqual(
            [
                "prepare",
                "message",
                "links",
                "run",
                "rollback",
                ("delete_targets", self.copied_objects),
            ],
            self.events,
        )

    async def test_enqueue_failure_returns_persisted_failed_run(self):
        async def enqueue(run_id):
            self.events.append(("enqueue", run_id))
            raise RuntimeError("redis unavailable")

        with (
            patch(
                "server.service.agent_run_service.enqueue_agent_run",
                side_effect=enqueue,
            ),
            patch.object(agent_run_service.logger, "exception"),
        ):
            run = await self.create_run(msg_metadata={})

        self.assertEqual("failed", run.agent_status)
        self.assertIn("redis unavailable", run.error)
        self.assertEqual(
            [
                "prepare",
                "message",
                "links",
                "run",
                "flush",
                "commit",
                ("delete_sources", []),
                ("enqueue", str(run.id)),
                ("set_failed", str(run.id)),
                "commit",
            ],
            self.events,
        )

    async def test_file_only_message_uses_attachment_type(self):
        async def enqueue(_):
            return None

        with patch(
            "server.service.agent_run_service.enqueue_agent_run",
            side_effect=enqueue,
        ):
            await self.create_run(
                query=None,
                msg_metadata={"attachment_file_ids": [str(FILE_ID_1)]},
            )

        self.assertEqual(
            "attachment",
            self.conversations.message_arguments["message_type"],
        )

    async def test_duplicate_ids_are_deduplicated_only_for_relations(self):
        async def enqueue(_):
            return None

        metadata = {
            "attachment_file_ids": [str(FILE_ID_1), str(FILE_ID_1)],
            "source": "web",
        }
        with patch(
            "server.service.agent_run_service.enqueue_agent_run",
            side_effect=enqueue,
        ):
            await self.create_run(msg_metadata=metadata)

        self.assertEqual(
            [str(FILE_ID_1)],
            self.prepare_arguments["file_ids"],
        )
        self.assertEqual(
            metadata,
            self.conversations.message_arguments["msg_metadata"],
        )
        self.assertEqual(
            [31],
            [attachment.id for attachment in self.links.arguments["attachments"]],
        )

    async def test_invalid_attachment_file_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "UUID4"):
            await self.create_run(
                msg_metadata={"attachment_file_ids": ["opaque-file-id"]},
            )

        self.assertEqual([], self.events)


class AgentRunEventTest(unittest.TestCase):
    def test_request_uses_message_metadata_without_attachment_field(self):
        self.assertIn("msg_metadata", AgentRunCreateRequest.model_fields)
        self.assertNotIn("attachment_ids", AgentRunCreateRequest.model_fields)

    def test_build_event_payload(self):
        payload = agent_run_service._build_agent_run_event(
            "r1",
            {"type": "status"},
        )

        self.assertEqual("agent_run", payload["scope"])
        self.assertEqual("r1", payload["run_id"])
        self.assertEqual("status", payload["type"])
        self.assertIn("created_at", payload)

    def test_decode_event_fields_from_redis_bytes(self):
        payload = agent_run_service._decode_event_fields(
            {b"event": b'{"type":"done"}'}
        )

        self.assertEqual({"type": "done"}, payload)


if __name__ == "__main__":
    unittest.main()
