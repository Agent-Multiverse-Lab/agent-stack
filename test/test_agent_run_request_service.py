"""agent_run_request_service 的 SQLite 单元测试。"""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from server.exception import AgentRunConflictError
from server.service import (
    agent_run_request_queue_service,
    agent_run_request_service,
    attachment_service,
)
from src.database.base import Base
from src.database.models import (
    Agent,
    AgentRun,
    AgentRunExecution,
    AgentRunRequest,
    Attachment,
    Conversation,
    Message,
    MessageAttachment,
    Project,
    ToolCall,
    User,
)
from src.database.repositories import AgentRunRepository, AgentRunRequestRepository


def _sqlite_async_adapter(db: Session):
    class AsyncSessionAdapter:
        def add(self, value):
            db.add(value)

        def add_all(self, values):
            db.add_all(values)

        async def get(self, model, key):
            return db.get(model, key)

        async def execute(self, statement):
            return db.execute(statement)

        async def scalar(self, statement):
            return db.scalar(statement)

        async def flush(self):
            db.flush()

        async def commit(self):
            db.commit()

        async def rollback(self):
            db.rollback()

    return AsyncSessionAdapter()


class AgentRunRequestServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        with self.engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            Base.metadata.create_all(
                connection,
                tables=[
                    model.__table__
                    for model in (
                        User,
                        Agent,
                        Project,
                        Conversation,
                        Message,
                        Attachment,
                        MessageAttachment,
                        ToolCall,
                        AgentRun,
                        AgentRunExecution,
                        AgentRunRequest,
                    )
                ],
            )
        self.db = Session(self.engine, expire_on_commit=False)
        self.addCleanup(self.db.close)

        self.file_id = str(uuid4())
        self.source = f"save/attachments/{self.file_id}"
        self.target = f"save/thread-1/attachments/{self.file_id}"
        self.db.add_all(
            [
                User(
                    id=7,
                    uid="user-1",
                    email="user1@example.test",
                    password_hash="unused",
                ),
                User(
                    id=8,
                    uid="user-2",
                    email="user2@example.test",
                    password_hash="unused",
                ),
                Agent(
                    slug="leader",
                    backend_id="test",
                    name="Leader",
                    role="orchestrator",
                    is_subagent=False,
                    internal_only=False,
                    enabled=True,
                    agent_config={"model": "test/initial"},
                ),
                Conversation(
                    id=1,
                    uid="user-1",
                    thread_id="thread-1",
                    agent_id="leader",
                    title="test",
                    conversation_metadata={
                        "model": "test/initial",
                        "workspace": "demo",
                    },
                ),
                Conversation(
                    id=2,
                    uid="user-1",
                    thread_id="thread-2",
                    agent_id="leader",
                    title="test-2",
                    conversation_metadata={"model": "test/initial"},
                ),
                Conversation(
                    id=3,
                    uid="user-2",
                    thread_id="thread-other",
                    agent_id="leader",
                    title="other",
                    conversation_metadata={"model": "test/initial"},
                ),
            ]
        )
        self.db.flush()
        self.db.add(
            Attachment(
                id=1,
                file_id=self.file_id,
                user_id=7,
                file_name="note.txt",
                content_type="text/plain",
                file_size=5,
                object_name=self.source,
            )
        )
        self.db.commit()

        self.session = _sqlite_async_adapter(self.db)
        self.user = SimpleNamespace(id=7, uid="user-1")
        self.other_user = SimpleNamespace(id=8, uid="user-2")
        self.enqueue_mock = AsyncMock()
        self.resolve_mock = AsyncMock(return_value=object())
        self.storage = SimpleNamespace(acopy_file=AsyncMock(), adelete_file=AsyncMock())

        for p in (
            patch.object(
                agent_run_request_service, "enqueue_agent_run", self.enqueue_mock
            ),
            patch.object(
                agent_run_request_service, "resolve_runtime_model", self.resolve_mock
            ),
            patch.object(
                agent_run_request_queue_service, "enqueue_agent_run", self.enqueue_mock
            ),
            patch.object(attachment_service, "get_storage", return_value=self.storage),
            patch.object(agent_run_request_queue_service.logger, "exception"),
        ):
            p.start()
            self.addCleanup(p.stop)

    async def _submit(self, **overrides):
        values = {
            "db": self.session,
            "current_user": self.user,
            "query": "分析附件",
            "agent_id": "leader",
            "thread_id": "thread-1",
            "request_metadata": {"type": "chat", "request_id": "req-1"},
            "image_content": None,
            "dispatch_policy": "enqueue",
        }
        values.update(overrides)
        return await agent_run_request_service.submit_agent_run_request(**values)

    def _counts(self) -> tuple[int, int, int, int]:
        return tuple(
            int(self.db.scalar(select(func.count()).select_from(model)) or 0)
            for model in (AgentRunRequest, Message, AgentRun, MessageAttachment)
        )

    async def test_idle_direct_submission_persists_model_attachments_message_and_run(
        self,
    ):
        run = await self._submit(
            request_metadata={
                "type": "chat",
                "request_id": "req-idle",
                "model": "test/switched",
                "attachment_file_ids": [self.file_id],
                "source": "web",
            }
        )
        self.assertIsInstance(run, AgentRun)
        self.assertEqual(run.agent_status, "pending")
        self.assertEqual(
            run.run_metadata,
            {
                "model": "test/switched",
                "workspace": "demo",
                "request_id": "req-idle",
            },
        )
        self.db.expire_all()

        conversation = self.db.get(Conversation, 1)
        self.assertEqual(conversation.conversation_metadata["model"], "test/switched")
        request = self.db.get(AgentRunRequest, "req-idle")
        self.assertEqual(request.status, "dispatched")
        self.assertIsNone(request.queue_seq)
        message = self.db.get(Message, request.trigger_message_id)
        self.assertEqual(message.status, "completed")
        self.assertEqual(message.agent_run_id, run.id)
        self.assertEqual(message.message_type, "multimodal")
        self.assertEqual(
            message.msg_metadata,
            {"attachment_file_ids": [self.file_id], "source": "web"},
        )
        self.assertEqual(self._counts(), (1, 1, 1, 1))
        self.storage.acopy_file.assert_awaited_once_with(
            attachment_service.ATTACHMENT_BUCKET_NAME,
            self.source,
            self.target,
        )
        self.storage.adelete_file.assert_awaited_once_with(
            attachment_service.ATTACHMENT_BUCKET_NAME,
            self.source,
        )
        self.enqueue_mock.assert_awaited_once_with(str(run.id))

    async def test_create_agent_run_request_direct_sets_queue_seq_for_active_run(self):
        conversation = self.db.get(Conversation, 1)
        blocker = await AgentRunRepository(self.session).create_run(
            run_id="run-active",
            thread_id="thread-1",
            conversation_id=1,
            uid="user-1",
            agent_slug="leader",
            request_id="blocking",
            trigger_message_id=None,
            agent_status="running",
        )
        copied: list[tuple[str, str]] = []
        queued_req = await agent_run_request_service.create_agent_run_request(
            db=self.session,
            conversation=conversation,
            uid="user-1",
            user_id=7,
            agent_id="leader",
            thread_id="thread-1",
            request_id="req-direct-1",
            query="hello",
            request_metadata={"type": "chat", "attachment_file_ids": [self.file_id]},
            image_content=None,
            dispatch_policy="enqueue",
            active_run=blocker,
            copied_objects=copied,
        )
        self.db.commit()
        self.assertEqual(copied, [(self.source, self.target)])
        self.assertEqual(queued_req.status, "queued")
        self.assertEqual(queued_req.queue_seq, 1)
        self.assertEqual(
            self.db.get(Message, queued_req.trigger_message_id).status, "queued"
        )

    async def test_busy_enqueue_steer_and_queued_retry_idempotency(self):
        await AgentRunRepository(self.session).create_run(
            run_id="blocker",
            thread_id="thread-1",
            conversation_id=1,
            uid="user-1",
            agent_slug="leader",
            request_id="blocking",
            trigger_message_id=None,
            agent_status="running",
        )
        self.db.commit()

        enqueued = await self._submit(
            query="first",
            request_metadata={"type": "chat", "request_id": "req-enq"},
            dispatch_policy="enqueue",
        )
        self.assertEqual(
            enqueued,
            {
                "run_id": None,
                "thread_id": "thread-1",
                "status": "queued",
                "dispatch_policy": "enqueue",
                "request_id": "req-enq",
                "queue_position": 1,
                "steering_run_id": None,
                "stream_url": None,
            },
        )

        steered = await self._submit(
            query="urgent",
            request_metadata={"type": "chat", "request_id": "req-steer"},
            dispatch_policy="steer",
        )
        self.assertEqual(steered["dispatch_policy"], "steer")
        self.assertEqual(steered["queue_position"], 1)
        self.assertEqual(steered["steering_run_id"], "blocker")

        retried = await self._submit(
            query="ignored-retry",
            request_metadata={"type": "chat", "request_id": "req-enq"},
            dispatch_policy="enqueue",
        )
        self.assertEqual(retried["request_id"], "req-enq")
        self.assertEqual(retried["queue_position"], 2)

        self.assertEqual(self._counts(), (2, 2, 1, 0))
        req_enq = self.db.get(AgentRunRequest, "req-enq")
        req_steer = self.db.get(AgentRunRequest, "req-steer")
        self.assertEqual((req_enq.status, req_enq.queue_seq), ("queued", 1))
        self.assertEqual((req_steer.status, req_steer.queue_seq), ("queued", 2))
        self.assertEqual(
            self.db.get(Message, req_enq.trigger_message_id).status, "queued"
        )
        self.assertEqual(
            self.db.get(Message, req_steer.trigger_message_id).status, "queued"
        )
        self.enqueue_mock.assert_not_awaited()

    async def test_busy_reject_and_pending_interaction_raise_conflict(self):
        blocker = await AgentRunRepository(self.session).create_run(
            run_id="blocker",
            thread_id="thread-1",
            conversation_id=1,
            uid="user-1",
            agent_slug="leader",
            request_id="blocking",
            trigger_message_id=None,
            agent_status="running",
        )
        self.db.commit()

        with self.assertRaisesRegex(AgentRunConflictError, "正在执行"):
            await self._submit(dispatch_policy="reject")
        self.assertEqual(self._counts(), (0, 0, 1, 0))

        blocker.agent_status = "interrupted"
        self.db.commit()
        for policy in ("enqueue", "reject", "steer"):
            with self.assertRaisesRegex(AgentRunConflictError, "待回答的问题"):
                await self._submit(
                    request_metadata={"type": "chat", "request_id": f"req-{policy}"},
                    dispatch_policy=policy,
                )
        self.assertEqual(self._counts(), (0, 0, 1, 0))
        self.enqueue_mock.assert_not_awaited()

    async def test_idempotency_conflicts_and_validation(self):
        with self.assertRaises(ValueError):
            await self._submit(thread_id="")
        with self.assertRaises(ValueError):
            await self._submit(request_metadata={"type": "resume", "request_id": "r"})
        with self.assertRaises(ValueError):
            await self._submit(dispatch_policy="invalid")
        with self.assertRaises(ValueError):
            await self._submit(request_metadata={"type": "chat", "model": 123})

        existing = await AgentRunRepository(self.session).create_run(
            run_id="run-done",
            thread_id="thread-1",
            conversation_id=1,
            uid="user-1",
            agent_slug="leader",
            request_id="req-done",
            trigger_message_id=None,
            agent_status="completed",
        )
        msg = Message(
            conversation_id=1, role="user", content="cancelled", status="cancelled"
        )
        self.db.add(msg)
        self.db.flush()
        await AgentRunRequestRepository(self.session).create_agent_run_request(
            request_id="req-cancelled",
            uid="user-1",
            thread_id="thread-1",
            agent_id="leader",
            trigger_message_id=msg.id,
            dispatch_policy="enqueue",
            status="cancelled",
            queue_seq=1,
        )
        self.db.commit()

        returned = await self._submit(
            request_metadata={"type": "chat", "request_id": "req-done"}
        )
        self.assertEqual(returned.id, existing.id)
        self.enqueue_mock.assert_not_awaited()

        with self.assertRaisesRegex(AgentRunConflictError, "request_id 已被其他请求使用"):
            await self._submit(
                thread_id="thread-2",
                request_metadata={"type": "chat", "request_id": "req-done"},
            )
        with self.assertRaisesRegex(AgentRunConflictError, "request_id 已被其他请求使用"):
            await self._submit(
                current_user=self.other_user,
                thread_id="thread-other",
                request_metadata={"type": "chat", "request_id": "req-done"},
            )
        with self.assertRaisesRegex(AgentRunConflictError, "请求已从等待区取消"):
            await self._submit(
                request_metadata={"type": "chat", "request_id": "req-cancelled"}
            )

    async def test_rollback_cleans_copied_target_without_deleting_source(self):
        with patch.object(
            AgentRunRequestRepository,
            "create_agent_run_request",
            AsyncMock(side_effect=RuntimeError("create failed")),
        ):
            with self.assertRaisesRegex(RuntimeError, "create failed"):
                await self._submit(
                    request_metadata={
                        "type": "chat",
                        "request_id": "req-fail",
                        "model": "test/switched",
                        "attachment_file_ids": [self.file_id],
                    }
                )
        self.db.expire_all()
        self.assertEqual(self._counts(), (0, 0, 0, 0))
        self.assertEqual(self.db.get(Attachment, 1).object_name, self.source)
        self.assertEqual(
            self.db.get(Conversation, 1).conversation_metadata["model"], "test/initial"
        )
        self.storage.adelete_file.assert_awaited_once_with(
            attachment_service.ATTACHMENT_BUCKET_NAME,
            self.target,
        )
        self.enqueue_mock.assert_not_awaited()

    async def test_enqueue_failure_after_commit_marks_unclaimed_run_failed(self):
        self.enqueue_mock.side_effect = RuntimeError("redis unavailable")
        run = await self._submit(
            request_metadata={"type": "chat", "request_id": "req-enqueue-fail"}
        )
        self.assertEqual(run.agent_status, "failed")
        self.assertEqual(run.error_type, "RuntimeError")
        self.assertIn("redis unavailable", run.error)

        self.db.expire_all()
        persisted = self.db.get(AgentRun, run.id)
        self.assertEqual(persisted.agent_status, "failed")
        self.assertEqual(persisted.error_type, "RuntimeError")
        self.enqueue_mock.assert_awaited_once_with(str(run.id))


if __name__ == "__main__":
    unittest.main()
