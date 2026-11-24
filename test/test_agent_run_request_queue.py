"""AgentRunRequestQueueRepository 与 agent_run_request_queue_service 的 SQLite 单元测试。"""

import unittest
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from server.exception import AgentRunConflictError
from server.service import agent_run_request_queue_service
from src.database.base import Base
from src.database.models import (
    AgentRun,
    AgentRunRequest,
    Conversation,
    Message,
    Project,
    ToolCall,
)
from src.database.repositories import (
    AgentRunRepository,
    AgentRunRequestQueueRepository,
    AgentRunRequestRepository,
)


def _sqlite_async_adapter(db: Session):
    class AsyncSessionAdapter:
        def add(self, value):
            db.add(value)

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


class AgentRunRequestQueueRepositoryTest(unittest.IsolatedAsyncioTestCase):
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
                        Project,
                        Conversation,
                        Message,
                        ToolCall,
                        AgentRun,
                        AgentRunRequest,
                    )
                ],
            )
        self.db = Session(self.engine, expire_on_commit=False)
        self.addCleanup(self.db.close)
        self.conversation = Conversation(
            id=1,
            uid="user-1",
            thread_id="thread-1",
            agent_id="leader",
            title="test",
            conversation_metadata={"model": "test/initial"},
        )
        self.db.add(self.conversation)
        self.db.flush()
        self.session = _sqlite_async_adapter(self.db)
        self.requests = AgentRunRequestRepository(self.session)
        self.queue = AgentRunRequestQueueRepository(self.session)

    def _add_message(self, content: str, *, status: str = "queued") -> Message:
        msg = Message(conversation_id=1, role="user", content=content, status=status)
        self.db.add(msg)
        self.db.flush()
        return msg

    async def test_queue_ordering_steer_expiry_cancel_and_convert(self):
        msg_1 = self._add_message("first enqueue")
        msg_2 = self._add_message("second cancel")
        msg_3 = self._add_message("third steer")
        msg_4 = self._add_message("direct", status="completed")

        req_1 = await self.requests.create_agent_run_request(
            request_id="req-1",
            uid="user-1",
            thread_id="thread-1",
            agent_id="leader",
            trigger_message_id=msg_1.id,
            dispatch_policy="enqueue",
            status="queued",
            queue_seq=await self.queue.get_next_queue_seq("thread-1"),
        )
        await self.requests.create_agent_run_request(
            request_id="req-2",
            uid="user-1",
            thread_id="thread-1",
            agent_id="leader",
            trigger_message_id=msg_2.id,
            dispatch_policy="enqueue",
            status="queued",
            queue_seq=await self.queue.get_next_queue_seq("thread-1"),
        )
        req_3 = await self.requests.create_agent_run_request(
            request_id="req-3",
            uid="user-1",
            thread_id="thread-1",
            agent_id="leader",
            trigger_message_id=msg_3.id,
            dispatch_policy="enqueue",
            status="queued",
            queue_seq=await self.queue.get_next_queue_seq("thread-1"),
        )
        req_4 = await self.requests.create_agent_run_request(
            request_id="req-4",
            uid="user-1",
            thread_id="thread-1",
            agent_id="leader",
            trigger_message_id=msg_4.id,
            dispatch_policy="enqueue",
            status="dispatched",
        )
        await AgentRunRepository(self.session).create_run(
            run_id="run-active",
            uid="user-1",
            conversation_id=1,
            thread_id="thread-1",
            agent_slug="leader",
            request_id="blocking",
            trigger_message_id=None,
            agent_status="running",
        )
        self.db.commit()

        # upgrade req-3 -> steer 优先排在队首
        self.assertFalse(await self.queue.has_queued_steer_for_thread("thread-1"))
        upgraded = await self.queue.upgrade_queued_to_steer("req-3", uid="user-1")
        self.assertEqual(upgraded.dispatch_policy, "steer")
        self.assertTrue(await self.queue.has_queued_steer_for_thread("thread-1"))
        self.assertEqual(await self.queue.get_queue_position("thread-1", "req-3", uid="user-1"), 1)
        self.assertEqual(await self.queue.get_queue_position("thread-1", "req-1", uid="user-1"), 2)

        # cancel req-2 同时软取消关联 Message
        cancelled = await self.queue.cancel_queued_request("req-2", uid="user-1")
        self.assertEqual(cancelled.status, "cancelled")
        self.db.commit()
        self.assertEqual(self.db.get(Message, msg_2.id).status, "cancelled")

        listed = await self.queue.list_queued_for_thread("thread-1", uid="user-1")
        self.assertEqual([item.request_id for item in listed], ["req-3", "req-1"])
        self.assertEqual(listed[0].trigger_message.content, "third steer")

        # 宽限超时判定
        self.assertFalse(await self.queue.has_expired_steer_for_run("run-active", grace_seconds=120))
        req_3.created_at = datetime.now(UTC) - timedelta(seconds=121)
        self.db.commit()
        self.assertTrue(await self.queue.has_expired_steer_for_run("run-active", grace_seconds=120))

        # 阻塞 Run 完成后才可将下一条转为 pending Run（单活部分唯一索引生效）
        self.db.get(AgentRun, "run-active").agent_status = "completed"
        self.db.commit()

        # pop_next_queued_for_thread 优先弹出 req-3 并通过 dispatch_request_to_run 转成 Run
        popped = await self.queue.pop_next_queued_for_thread("thread-1")
        self.assertEqual(popped.request_id, "req-3")
        promoted_run = await self.queue.dispatch_request_to_run(
            request=popped,
            conversation=self.conversation,
            run_metadata={"model": "test/initial", "request_id": "req-3"},
            run_id="run-promoted",
        )
        self.db.commit()
        self.assertEqual(promoted_run.id, "run-promoted")
        self.assertEqual(self.db.get(AgentRunRequest, "req-3").status, "dispatched")
        msg_3_db = self.db.get(Message, msg_3.id)
        self.assertEqual((msg_3_db.status, msg_3_db.agent_run_id), ("completed", "run-promoted"))

        # 非 queued 请求直接转换仅绑定 Message.agent_run_id
        self.db.get(AgentRun, "run-promoted").agent_status = "completed"
        self.db.commit()
        direct_run = await self.queue.dispatch_request_to_run(
            request=req_4,
            conversation=self.conversation,
            run_metadata={"model": "test/initial", "request_id": "req-4"},
            run_id="run-direct",
        )
        self.db.commit()
        self.db.expire_all()
        self.assertEqual(self.db.get(Message, msg_4.id).agent_run_id, direct_run.id)
        self.assertIsNotNone(req_1)


class AgentRunRequestQueueServiceTest(unittest.IsolatedAsyncioTestCase):
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
                        Project,
                        Conversation,
                        Message,
                        ToolCall,
                        AgentRun,
                        AgentRunRequest,
                    )
                ],
            )
        self.db = Session(self.engine, expire_on_commit=False)
        self.addCleanup(self.db.close)
        self.db.add(
            Conversation(
                id=1,
                uid="user-1",
                thread_id="thread-1",
                agent_id="leader",
                title="test",
                conversation_metadata={"model": "test/initial"},
            )
        )
        self.db.flush()
        self.session = _sqlite_async_adapter(self.db)
        self.enqueue_mock = AsyncMock()
        self.resolve_mock = AsyncMock(return_value=object())

        @asynccontextmanager
        async def fake_ctx():
            yield self.session

        for p in (
            patch.object(agent_run_request_queue_service, "session_context", fake_ctx),
            patch.object(agent_run_request_queue_service, "enqueue_agent_run", self.enqueue_mock),
            patch.object(agent_run_request_queue_service, "validate_model", self.resolve_mock),
        ):
            p.start()
            self.addCleanup(p.stop)

    async def test_dispatch_cancel_and_steer_services(self):
        user = SimpleNamespace(id=7, uid="user-1")
        other = SimpleNamespace(id=8, uid="user-2")
        msg_1 = Message(conversation_id=1, role="user", content="one", status="queued")
        msg_2 = Message(conversation_id=1, role="user", content="two", status="queued")
        self.db.add_all([msg_1, msg_2])
        self.db.flush()
        requests = AgentRunRequestRepository(self.session)
        await requests.create_agent_run_request(
            request_id="req-1", uid="user-1", thread_id="thread-1",
            agent_id="leader", trigger_message_id=msg_1.id,
            dispatch_policy="enqueue", status="queued", queue_seq=1,
        )
        await requests.create_agent_run_request(
            request_id="req-2", uid="user-1", thread_id="thread-1",
            agent_id="leader", trigger_message_id=msg_2.id,
            dispatch_policy="enqueue", status="queued", queue_seq=2,
        )
        blocker = await AgentRunRepository(self.session).create_run(
            run_id="run-active", uid="user-1", conversation_id=1,
            thread_id="thread-1", agent_slug="leader",
            request_id="blocking", trigger_message_id=None, agent_status="running",
        )
        self.db.commit()

        # 他人取消返回 404 (LookupError)
        with self.assertRaises(LookupError):
            await agent_run_request_queue_service.cancel_queued_request(
                db=self.session, current_user=other, request_id="req-1",
            )

        # 会话忙碌：dispatch_next_queued_request 不出队；steer_queued 原地升级为 202
        self.assertIsNone(
            await agent_run_request_queue_service.dispatch_next_queued_request("thread-1")
        )
        upgraded = await agent_run_request_queue_service.steer_queued_request(
            db=self.session, current_user=user, request_id="req-2",
        )
        self.assertEqual(upgraded.dispatch_policy, "steer")
        self.assertEqual(upgraded.queue_position, 1)
        self.assertEqual(upgraded.steering_run_id, blocker.id)

        # 取消 req-1 + 幂等重复取消
        cancelled = await agent_run_request_queue_service.cancel_queued_request(
            db=self.session, current_user=user, request_id="req-1",
        )
        self.assertEqual(cancelled, {"request_id": "req-1", "status": "cancelled"})
        self.assertEqual(
            await agent_run_request_queue_service.cancel_queued_request(
                db=self.session, current_user=user, request_id="req-1",
            ),
            cancelled,
        )
        with self.assertRaises(AgentRunConflictError):
            await agent_run_request_queue_service.steer_queued_request(
                db=self.session, current_user=user, request_id="req-1",
            )

        # 阻塞 Run 完成后，dispatch_next_queued_request 晋升 req-2 并入 ARQ
        blocker.agent_status = "completed"
        self.db.commit()
        dispatched_run = await agent_run_request_queue_service.dispatch_next_queued_request(
            "thread-1"
        )
        self.assertIsNotNone(dispatched_run)
        self.assertEqual(dispatched_run.request_id, "req-2")
        self.enqueue_mock.assert_awaited_once_with(str(dispatched_run.id))

        # 已晋升的请求再调用 cancel / steer 返回带 run_id 的冲突
        with self.assertRaises(AgentRunConflictError) as cancel_conflict:
            await agent_run_request_queue_service.cancel_queued_request(
                db=self.session, current_user=user, request_id="req-2",
            )
        self.assertEqual(cancel_conflict.exception.run_id, dispatched_run.id)

        with self.assertRaises(AgentRunConflictError) as steer_conflict:
            await agent_run_request_queue_service.steer_queued_request(
                db=self.session, current_user=user, request_id="req-2",
            )
        self.assertEqual(steer_conflict.exception.run_id, dispatched_run.id)

    async def test_unresumed_interrupted_blocks_dispatch_and_steer_until_cancelled(self):
        user = SimpleNamespace(id=7, uid="user-1")
        msg = Message(conversation_id=1, role="user", content="queued after interrupt", status="queued")
        self.db.add(msg)
        self.db.flush()
        await AgentRunRequestRepository(self.session).create_agent_run_request(
            request_id="req-after-int",
            uid="user-1",
            thread_id="thread-1",
            agent_id="leader",
            trigger_message_id=msg.id,
            dispatch_policy="enqueue",
            status="queued",
            queue_seq=1,
        )
        interrupted = await AgentRunRepository(self.session).create_run(
            run_id="run-int",
            uid="user-1",
            conversation_id=1,
            thread_id="thread-1",
            agent_slug="leader",
            request_id="req-int",
            trigger_message_id=None,
            agent_status="interrupted",
        )
        self.db.commit()

        self.assertIsNone(
            await agent_run_request_queue_service.dispatch_next_queued_request("thread-1")
        )
        with self.assertRaisesRegex(AgentRunConflictError, "待回答的问题"):
            await agent_run_request_queue_service.steer_queued_request(
                db=self.session, current_user=user, request_id="req-after-int",
            )

        cancelled = await AgentRunRepository(self.session).request_cancel(interrupted.id)
        self.db.commit()
        self.assertEqual(cancelled.agent_status, "cancelled")

        dispatched = await agent_run_request_queue_service.dispatch_next_queued_request("thread-1")
        self.assertIsNotNone(dispatched)
        self.assertEqual(dispatched.request_id, "req-after-int")
        self.enqueue_mock.assert_awaited_once_with(str(dispatched.id))
