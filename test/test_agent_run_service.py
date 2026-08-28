"""Agent Run 创建事务与事件辅助函数测试。"""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from server.entities.agent import AgentRunCreateRequest
from server.service import agent_run_service
from server.service.arq_queue_servcie import build_agent_chunk_envolope
from server.utils.agent_run_utils import format_agent_run_sse

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

    # FIXEME: 普通 Run 创建测试默认没有待回答 interaction。
    async def get_pending_interaction_run(self, **_values):
        return None

    async def set_agent_terminal(
        self,
        run_id,
        *,
        status,
        error=None,
        error_type=None,
    ):
        self.events.append(("set_agent_terminal", run_id, status))
        self.run.agent_status = status
        self.run.error = error
        self.run.error_type = error_type
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
        self.assertEqual("RuntimeError", run.error_type)
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
                ("set_agent_terminal", str(run.id), "failed"),
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

    async def test_selected_model_is_persisted_in_run_metadata(self):
        async def enqueue(_):
            return None

        with patch(
            "server.service.agent_run_service.enqueue_agent_run",
            side_effect=enqueue,
        ):
            await self.create_run(
                thread_metadata={
                    "request_id": "request-1",
                    "model": "dashscope/qwen3.8-max",
                }
            )

        self.assertEqual(
            "dashscope/qwen3.8-max",
            self.runs.arguments["run_metadata"]["model"],
        )

    async def test_unavailable_model_is_rejected_before_writes(self):
        with self.assertRaisesRegex(ValueError, "可用模型目录"):
            await self.create_run(
                thread_metadata={
                    "model": "gemini/gemini-3-pro",
                }
            )

        self.assertEqual([], self.events)


class AgentRunEventTest(unittest.IsolatedAsyncioTestCase):
    def test_request_uses_message_metadata_without_attachment_field(self):
        self.assertIn("msg_metadata", AgentRunCreateRequest.model_fields)
        self.assertNotIn("attachment_ids", AgentRunCreateRequest.model_fields)
        self.assertNotIn("is_resume", AgentRunCreateRequest.model_fields)
        self.assertNotIn("parent_run_id", AgentRunCreateRequest.model_fields)

    def test_format_sse_uses_queue_envelope(self):
        envelope = build_agent_chunk_envolope(
            run_id="r1",
            event_type="end",
            thread_id="thread-1",
            payload={"status": "completed"},
            created_at="2026-08-16T00:00:00+00:00",
        )
        frame = format_agent_run_sse("1-0", envelope)
        data = json.loads(
            next(line for line in frame.splitlines() if line.startswith("data: "))[6:]
        )

        self.assertIn("id: 1-0\n", frame)
        self.assertIn("event: end\n", frame)
        self.assertEqual("agent_run", data["scope"])
        self.assertEqual("r1", data["run_id"])
        self.assertEqual("end", data["type"])
        self.assertEqual("completed", data["status"])

    def test_decode_event_fields_from_redis_bytes(self):
        payload = agent_run_service._decode_event_fields(
            {b"event": b'{"type":"done"}'}
        )

        self.assertEqual({"type": "done"}, payload)

    async def test_subagent_progress_reads_nested_payload(self):
        envelope = build_agent_chunk_envolope(
            run_id="r1",
            event_type="end",
            thread_id="thread-1",
            payload={"status": "failed", "error": "boom"},
            created_at="2026-08-16T00:00:00+00:00",
        )
        fields = {b"event": json.dumps(envelope).encode()}

        with patch(
            "server.service.agent_run_service.read_recent_agent_run_stream_events",
            return_value=[(b"1-0", fields)],
        ):
            progress = await agent_run_service.read_subagent_progress(run_id="r1")

        self.assertEqual("failed", progress["status"])
        self.assertTrue(progress["terminal"])
        self.assertEqual("boom", progress["error"])
        self.assertEqual(envelope, progress["events"][0]["payload"])


if __name__ == "__main__":
    unittest.main()
