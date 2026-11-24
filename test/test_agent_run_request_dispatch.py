"""请求持久化与派发的 SQLite 验证及独立 PostgreSQL schema 集成测试。"""

import asyncio
import importlib.util
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, delete, func, inspect, select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from server.exception import AgentRunConflictError
from server.service import (
    agent_run_request_queue_service,
    agent_run_request_service,
    attachment_service,
)
from src.configs import config
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
from src.database.repositories import (
    AgentRunRepository,
    AgentRunRequestQueueRepository,
    AgentRunRequestRepository,
    ConversationRepository,
)

MIGRATION_PATH = Path(__file__).resolve().parents[1] / "migrate/versions/0028_agent_run_request.py"
spec = importlib.util.spec_from_file_location("run_request_migration", MIGRATION_PATH)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)

queue_spec = importlib.util.spec_from_file_location("queue_migration", MIGRATION_PATH.with_name("0031_request_dispatch_queue.py"))
queue_migration = importlib.util.module_from_spec(queue_spec)
queue_spec.loader.exec_module(queue_migration)


class AgentRunRequestRepositoryTest(unittest.IsolatedAsyncioTestCase):
    """用 SQLite 验证实际 SQL 与迁移；PostgreSQL 行锁竞争由下方集成测试验证。"""

    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        with self.engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            Base.metadata.create_all(connection, tables=[
                model.__table__ for model in (Project, Conversation, Message, ToolCall, AgentRun, AgentRunRequest)
            ])
        self.db = Session(self.engine, expire_on_commit=False)
        self.addCleanup(self.db.close)
        self.db.add(Conversation(
            id=1, uid="user-1", thread_id="thread-1", agent_id="leader", title="test",
            conversation_metadata={"model": "test/initial"},
        ))
        self.db.flush()
        self.db.add(Message(
            id=1, conversation_id=1, role="user", content="original",
            image_content="image", msg_metadata={"source": "test"},
        ))
        self.db.commit()
        db = self.db

        class AsyncSessionAdapter:
            def add(self, value):
                db.add(value)

            async def execute(self, statement):
                return db.execute(statement)

            async def flush(self):
                db.flush()

        self.session = AsyncSessionAdapter()
        self.repository = AgentRunRequestRepository(self.session)
        self.queue = AgentRunRequestQueueRepository(self.session)

    @staticmethod
    def migrate(connection, action):
        with patch.object(migration, "op", Operations(MigrationContext.configure(connection))):
            getattr(migration, action)()

    async def create_request(self):
        return await self.repository.create_agent_run_request(
            request_id="request-1", uid="user-1", thread_id="thread-1",
            agent_id="leader", trigger_message_id=1, dispatch_policy="reject", status="dispatched",
        )

    async def test_reads_request_and_current_conversation_configuration(self):
        await self.create_request()
        self.db.commit()
        self.db.execute(update(Conversation).values(conversation_metadata={"model": "test/changed"}))
        self.db.commit()
        request = await self.repository.get_run_request_by_request_id("request-1")
        conversation = await ConversationRepository(self.session).get_conversation_by_thread_id_for_user(
            thread_id=request.thread_id, user_id=request.uid, for_update=True,
        )
        self.assertEqual(conversation.conversation_metadata, {"model": "test/changed"})
        self.assertEqual(request.trigger_message_id, 1)
        message = self.db.get(Message, request.trigger_message_id)
        self.assertEqual((message.content, message.image_content, message.msg_metadata), (
            "original", "image", {"source": "test"},
        ))
        self.assertEqual(set(AgentRunRequest.__table__.columns.keys()), {
            "request_id", "uid", "thread_id", "agent_id", "trigger_message_id", "created_at",
            "dispatch_policy", "status", "queue_seq",
        })

    async def test_run_rollback_preserves_request_and_leaves_message_unbound(self):
        await self.create_request()
        self.db.commit()
        run = await AgentRunRepository(self.session).create_run(
            run_id="run-1", uid="user-1", conversation_id=1, thread_id="thread-1",
            agent_slug="leader", request_id="request-1", trigger_message_id=1,
        )
        await ConversationRepository(self.session).bind_input_message_to_run(run)
        self.db.rollback()
        self.assertIsNotNone(await self.repository.get_run_request_by_request_id("request-1"))
        self.assertIsNone(self.db.get(Message, 1).agent_run_id)
        self.assertIsNone(self.db.get(AgentRun, "run-1"))

    async def test_repository_does_not_commit_and_message_delete_cascades(self):
        await self.create_request()
        self.db.rollback()
        self.assertIsNone(await self.repository.get_run_request_by_request_id("request-1"))
        await self.create_request()
        self.db.commit()
        self.db.execute(delete(Message))
        self.db.commit()
        self.assertIsNone(await self.repository.get_run_request_by_request_id("request-1"))

    async def test_enqueue_does_not_trigger_steer_and_pops_in_fifo_order(self):
        from datetime import UTC, datetime, timedelta

        await AgentRunRepository(self.session).create_run(
            run_id="run-active", uid="user-1", conversation_id=1, thread_id="thread-1",
            agent_slug="leader", request_id="blocking-request", trigger_message_id=None,
            agent_status="running",
        )
        await self.repository.create_agent_run_request(
            request_id="request-enqueue", uid="user-1", thread_id="thread-1",
            agent_id="leader", trigger_message_id=1, dispatch_policy="enqueue",
            status="queued", queue_seq=await self.queue.get_next_queue_seq("thread-1"),
        )
        self.db.execute(
            update(AgentRunRequest)
            .where(AgentRunRequest.request_id == "request-enqueue")
            .values(created_at=datetime.now(UTC) - timedelta(seconds=121))
        )
        self.db.commit()

        self.assertFalse(await self.queue.has_queued_steer_for_thread("thread-1"))
        self.assertFalse(await self.queue.has_expired_steer_for_run("run-active", grace_seconds=120))

        await self.repository.create_agent_run_request(
            request_id="request-steer", uid="user-1", thread_id="thread-1",
            agent_id="leader", trigger_message_id=1, dispatch_policy="steer",
            status="queued", queue_seq=await self.queue.get_next_queue_seq("thread-1"),
        )
        self.db.commit()
        self.assertTrue(await self.queue.has_queued_steer_for_thread("thread-1"))

        listed = await self.queue.list_queued_for_thread("thread-1", uid="user-1")
        self.assertEqual([item.request_id for item in listed], ["request-steer", "request-enqueue"])
        self.assertEqual(listed[0].trigger_message.content, "original")

        first = await self.queue.pop_next_queued_for_thread("thread-1")
        self.assertEqual(first.request_id, "request-steer")
        await self.queue.mark_dispatched(first.request_id)
        second = await self.queue.pop_next_queued_for_thread("thread-1")
        self.assertEqual(second.request_id, "request-enqueue")
        await self.queue.mark_dispatched(second.request_id)
        self.assertIsNone(await self.queue.pop_next_queued_for_thread("thread-1"))
        self.db.commit()

    async def test_upgrade_cancel_and_list_messages_filter(self):
        msg_cancelled = Message(
            conversation_id=1, role="user", content="drop me", status="queued",
        )
        self.db.add(msg_cancelled)
        self.db.flush()
        msg_steer = Message(
            conversation_id=1, role="user", content="steer me", status="queued",
        )
        self.db.add(msg_steer)
        self.db.flush()

        await self.repository.create_agent_run_request(
            request_id="req-cancel", uid="user-1", thread_id="thread-1",
            agent_id="leader", trigger_message_id=msg_cancelled.id,
            dispatch_policy="enqueue", status="queued", queue_seq=1,
        )
        await self.repository.create_agent_run_request(
            request_id="req-upgrade", uid="user-1", thread_id="thread-1",
            agent_id="leader", trigger_message_id=msg_steer.id,
            dispatch_policy="enqueue", status="queued", queue_seq=2,
        )
        self.db.commit()

        upgraded = await self.queue.upgrade_queued_to_steer("req-upgrade", uid="user-1")
        self.assertIsNotNone(upgraded)
        self.assertEqual(upgraded.dispatch_policy, "steer")
        self.assertIsNone(await self.queue.upgrade_queued_to_steer("req-upgrade", uid="other"))

        cancelled = await self.queue.cancel_queued_request("req-cancel", uid="user-1")
        self.assertIsNotNone(cancelled)
        self.assertEqual(cancelled.status, "cancelled")
        self.db.commit()
        self.db.expire_all()

        self.assertEqual(self.db.get(Message, msg_cancelled.id).status, "cancelled")
        listed = await self.queue.list_queued_for_thread("thread-1", uid="user-1")
        self.assertEqual([item.request_id for item in listed], ["req-upgrade"])

        conversations = ConversationRepository(self.session)
        visible = await conversations.list_messages(conversation_id=1, limit=10)
        self.assertEqual([item.id for item in visible], [1])



@unittest.skipUnless(
    os.environ.get("RUN_REQUEST_DISPATCH_TEST") == "1",
    "设置 RUN_REQUEST_DISPATCH_TEST=1 执行 PostgreSQL 请求派发测试",
)
class AgentRunRequestDispatchTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.schema = "test_run_request_" + uuid4().hex
        self.admin = create_async_engine(config.database_url)
        self.addAsyncCleanup(self.admin.dispose)
        async with self.admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.addAsyncCleanup(self.drop_schema)
        self.engine = create_async_engine(
            config.database_url,
            connect_args={"server_settings": {"search_path": self.schema}},
        )
        self.addAsyncCleanup(self.engine.dispose)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(lambda db: Base.metadata.create_all(db, tables=[
                model.__table__ for model in (
                    User, Agent, Project, Conversation, Message, AgentRun, AgentRunExecution,
                    Attachment, MessageAttachment, ToolCall,
                )
            ]))
            await connection.run_sync(self.migrate, "upgrade")
            await connection.run_sync(self.migrate_queue, "upgrade")
        self.file_id = str(uuid4())
        self.source = f"save/attachments/{self.file_id}"
        self.target = f"save/thread-1/attachments/{self.file_id}"
        async with self.sessions() as db:
            db.add(User(id=7, uid="user-1", email="request@example.test", password_hash="unused"))
            db.add(Agent(
                slug="leader", backend_id="test", name="test", internal_only=False,
                agent_config={"model": "test/initial"},
            ))
            db.add_all([
                Conversation(
                    id=index, uid="user-1", thread_id=f"thread-{index}", agent_id="leader",
                    title="test", conversation_metadata={"model": "test/initial", "workspace": "demo"},
                )
                for index in (1, 2)
            ])
            await db.flush()
            db.add(Attachment(
                id=1, file_id=self.file_id, user_id=7, file_name="input.txt",
                content_type="text/plain", file_size=3, object_name=self.source,
            ))
            await db.commit()
        self.enqueue = AsyncMock()
        self.model = AsyncMock(return_value=object())
        self.storage = SimpleNamespace(acopy_file=AsyncMock(), adelete_file=AsyncMock())
        for current in (
            patch.object(agent_run_request_service, "enqueue_agent_run", self.enqueue),
            patch.object(agent_run_request_service, "validate_model", self.model),
            patch.object(agent_run_request_queue_service, "enqueue_agent_run", self.enqueue),
            patch.object(agent_run_request_queue_service, "validate_model", self.model),
            patch.object(attachment_service, "get_storage", return_value=self.storage),
            patch.object(agent_run_request_queue_service.logger, "exception"),
        ):
            current.start()
            self.addCleanup(current.stop)

    async def drop_schema(self):
        async with self.admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))

    @staticmethod
    def migrate(connection, action):
        with patch.object(migration, "op", Operations(MigrationContext.configure(connection))):
            getattr(migration, action)()

    @staticmethod
    def migrate_queue(connection, action):
        with patch.object(queue_migration, "op", Operations(MigrationContext.configure(connection))):
            getattr(queue_migration, action)()

    async def submit(self, request_id="request-1", *, db=None, **changes):
        values = {
            "current_user": SimpleNamespace(id=7, uid="user-1"),
            "query": "原始输入", "agent_id": "leader", "thread_id": "thread-1",
            "request_metadata": {"type": "chat", "request_id": request_id},
            "image_content": "https://example.test/input.png",
        }
        values.update(changes)
        if db is not None:
            return await agent_run_request_service.submit_agent_run_request(db=db, **values)
        async with self.sessions() as session:
            return await agent_run_request_service.submit_agent_run_request(db=session, **values)

    async def counts(self):
        async with self.sessions() as db:
            return tuple([
                await db.scalar(select(func.count()).select_from(model))
                for model in (AgentRunRequest, Message, AgentRun, MessageAttachment)
            ])

    async def add_blocking_run(self, status="running"):
        async with self.sessions() as db:
            run = await AgentRunRepository(db).create_run(
                run_id="blocker", thread_id="thread-1", conversation_id=1,
                uid="user-1", agent_slug="leader", request_id="blocking-request",
                trigger_message_id=None, agent_status=status,
            )
            await db.commit()
            return run

    async def test_enqueue_sees_committed_request_message_attachment_and_run(self):
        async def enqueue(run_id):
            async with self.sessions() as observer:
                request = await observer.get(AgentRunRequest, "request-1")
                run = await observer.get(AgentRun, run_id)
                message = await observer.get(Message, request.trigger_message_id)
                self.assertEqual(message.id, run.trigger_message_id)
                self.assertEqual(run.id, message.agent_run_id)
                self.assertEqual(message.content, "原始输入")
                self.assertEqual(message.image_content, "https://example.test/input.png")
                self.assertEqual(message.msg_metadata["attachment_file_ids"], [self.file_id])
                self.assertEqual(run.run_metadata, {
                    "model": "test/initial", "workspace": "demo", "request_id": "request-1",
                })
                self.assertEqual(await observer.scalar(select(func.count()).select_from(MessageAttachment)), 1)
        self.enqueue.side_effect = enqueue
        await self.submit(request_metadata={"type": "chat", "request_id": "request-1", "attachment_file_ids": [self.file_id]})
        self.assertEqual(await self.counts(), (1, 1, 1, 1))
        self.storage.adelete_file.assert_awaited_once_with(attachment_service.ATTACHMENT_BUCKET_NAME, self.source)

    async def test_busy_reject_does_not_save_input(self):
        await self.add_blocking_run()
        with self.assertRaisesRegex(AgentRunConflictError, "正在执行"):
            await self.submit(dispatch_policy="reject")
        self.assertEqual(await self.counts(), (0, 0, 1, 0))
        self.enqueue.assert_not_awaited()

    async def promote(self):
        from contextlib import asynccontextmanager
        @asynccontextmanager
        async def session_context():
            async with self.sessions() as db:
                yield db
        with patch.object(agent_run_request_queue_service, "session_context", session_context):
            return await agent_run_request_queue_service.dispatch_next_queued_request("thread-1")

    async def finish_blocker(self):
        async with self.sessions() as db:
            await db.execute(update(AgentRun).where(AgentRun.id == "blocker").values(agent_status="completed"))
            await db.commit()

    async def test_default_enqueue_queues_without_steering_and_promotes_after_completion(self):
        await self.add_blocking_run()
        queued = await self.submit()
        self.assertEqual(queued["status"], "queued")
        self.assertEqual(queued["dispatch_policy"], "enqueue")
        self.assertEqual(queued["queue_position"], 1)
        self.assertIsNone(queued["steering_run_id"])
        async with self.sessions() as db:
            self.assertFalse(await AgentRunRequestQueueRepository(db).has_queued_steer_for_thread("thread-1"))
        self.assertIsNone(await self.promote())
        await self.finish_blocker()
        run = await self.promote()
        self.assertIsNotNone(run)
        self.assertEqual(run.request_id, "request-1")
        self.enqueue.assert_awaited_once()

    async def test_soft_cancel_and_steer_upgrade_contracts(self):
        user = SimpleNamespace(id=7, uid="user-1")
        await self.add_blocking_run()
        await self.submit("req-1", query="first", dispatch_policy="enqueue")
        second = await self.submit("req-2", query="second", dispatch_policy="enqueue")
        self.assertEqual(second["queue_position"], 2)

        async with self.sessions() as db:
            upgraded = await agent_run_request_queue_service.steer_queued_request(
                db=db, current_user=user, request_id="req-2",
            )
            self.assertEqual(upgraded["dispatch_policy"], "steer")
            self.assertEqual(upgraded["queue_position"], 1)
            self.assertEqual(upgraded["steering_run_id"], "blocker")

        async with self.sessions() as db:
            cancelled = await agent_run_request_queue_service.cancel_queued_request(
                db=db, current_user=user, request_id="req-1",
            )
            self.assertEqual(cancelled, {"request_id": "req-1", "status": "cancelled"})
            again = await agent_run_request_queue_service.cancel_queued_request(
                db=db, current_user=user, request_id="req-1",
            )
            self.assertEqual(again["status"], "cancelled")

        with self.assertRaisesRegex(AgentRunConflictError, "取消"):
            await self.submit("req-1")

        await self.finish_blocker()
        async with self.sessions() as db:
            promoted = await agent_run_request_queue_service.steer_queued_request(
                db=db, current_user=user, request_id="req-2",
            )
            self.assertEqual(promoted.request_id, "req-2")

        async with self.sessions() as db:
            with self.assertRaises(AgentRunConflictError) as conflict:
                await agent_run_request_queue_service.cancel_queued_request(
                    db=db, current_user=user, request_id="req-2",
                )
            self.assertEqual(conflict.exception.run_id, promoted.id)

        async with self.sessions() as db:
            with self.assertRaises(AgentRunConflictError) as steer_conflict:
                await agent_run_request_queue_service.steer_queued_request(
                    db=db, current_user=user, request_id="req-2",
                )
            self.assertEqual(steer_conflict.exception.run_id, promoted.id)

    async def test_steer_retry_and_promotion_use_original_input_and_current_model(self):
        await self.add_blocking_run()
        queued = await self.submit(dispatch_policy="steer")
        self.assertEqual(queued["steering_run_id"], "blocker")
        self.assertEqual((await self.submit(query="changed", dispatch_policy="steer"))["status"], "queued")
        async with self.sessions() as db:
            self.assertEqual(await ConversationRepository(db).list_messages(conversation_id=1, limit=10), [])
            await db.execute(update(Conversation).values(conversation_metadata={"model": "test/changed"}))
            await db.commit()
        self.assertIsNone(await self.promote())
        await self.finish_blocker()
        first, second = await asyncio.gather(self.promote(), self.promote())
        run = first or second
        self.assertTrue(first is None or second is None)
        self.assertEqual(run.run_metadata["model"], "test/changed")
        async with self.sessions() as db:
            message = await db.get(Message, run.trigger_message_id)
            self.assertEqual((message.content, message.status, message.agent_run_id), ("原始输入", "completed", run.id))
            self.assertGreater(message.sequence, 1)
        self.assertEqual((await self.submit()).id, run.id)
        self.enqueue.assert_awaited_once()

    async def test_promoted_input_follows_previous_output_in_paginated_history(self):
        await self.add_blocking_run()
        await self.submit(dispatch_policy="steer")
        async with self.sessions() as db:
            output = Message(conversation_id=1, role="assistant", agent_run_id="blocker", content="previous answer")
            db.add(output)
            await db.commit()
            output_id = output.id
        await self.finish_blocker()
        run = await self.promote()
        async with self.sessions() as db:
            repo = ConversationRepository(db)
            latest = await repo.list_messages(conversation_id=1, limit=1)
            self.assertEqual(latest[0].id, run.trigger_message_id)
            older = await repo.list_messages(conversation_id=1, limit=1, before_message_id=latest[0].id)
            self.assertEqual(older[0].id, output_id)

    async def test_grace_timeout_uses_queued_steer(self):
        from datetime import UTC, datetime, timedelta
        await self.add_blocking_run()
        await self.submit(dispatch_policy="steer")
        async with self.sessions() as db:
            repo = AgentRunRequestQueueRepository(db)
            self.assertFalse(await repo.has_expired_steer_for_run("blocker", grace_seconds=120))
            await db.execute(update(AgentRunRequest).values(created_at=datetime.now(UTC) - timedelta(seconds=121)))
            await db.commit()
            self.assertTrue(await repo.has_expired_steer_for_run("blocker", grace_seconds=120))

    async def test_pending_interaction_rejects_without_input(self):
        await self.add_blocking_run("interrupted")
        for policy in ("enqueue", "reject", "steer"):
            with self.assertRaisesRegex(AgentRunConflictError, "待回答"):
                await self.submit(dispatch_policy=policy)
        self.assertEqual(await self.counts(), (0, 0, 1, 0))
        self.enqueue.assert_not_awaited()

    async def test_reception_failure_rolls_back_input_links_and_copied_target(self):
        with patch.object(AgentRunRequestRepository, "create_request", AsyncMock(side_effect=RuntimeError("receive failed"))):
            with self.assertRaisesRegex(RuntimeError, "receive failed"):
                await self.submit(request_metadata={"type": "chat", "request_id": "request-1", "attachment_file_ids": [self.file_id]})
        self.assertEqual(await self.counts(), (0, 0, 0, 0))
        self.storage.adelete_file.assert_awaited_once_with(attachment_service.ATTACHMENT_BUCKET_NAME, self.target)
        async with self.sessions() as db:
            self.assertEqual((await db.get(Attachment, 1)).object_name, self.source)
        self.enqueue.assert_not_awaited()

    async def test_run_creation_failure_rolls_back_received_input(self):
        with patch.object(AgentRunRepository, "create_run", AsyncMock(side_effect=RuntimeError("create failed"))):
            with self.assertRaisesRegex(RuntimeError, "create failed"):
                await self.submit()
        self.assertEqual(await self.counts(), (0, 0, 0, 0))
        await self.submit()
        self.assertEqual(await self.counts(), (1, 1, 1, 0))

    async def test_enqueue_failure_marks_only_unclaimed_run_failed(self):
        self.enqueue.side_effect = RuntimeError("redis unavailable")
        run = await self.submit()
        self.assertEqual(run.agent_status, "failed")
        self.assertEqual(run.error_type, "RuntimeError")
        self.assertIn("redis unavailable", run.error)
        self.assertEqual(await self.counts(), (1, 1, 1, 0))
        self.assertEqual((await self.submit()).id, run.id)
        self.enqueue.assert_awaited_once()

    async def test_enqueue_error_after_worker_claim_does_not_overwrite_running(self):
        async def enqueue(run_id):
            async with self.sessions() as worker:
                await AgentRunRepository(worker).set_running(run_id, worker_id="worker-1")
                await worker.commit()
            raise RuntimeError("response lost")
        self.enqueue.side_effect = enqueue
        run = await self.submit()
        self.assertEqual(run.agent_status, "running")
        self.assertEqual(run.worker_id, "worker-1")
        self.assertIsNone(run.error)

    async def test_same_request_concurrently_creates_one_input_and_one_run(self):
        first, second = await asyncio.wait_for(asyncio.gather(self.submit(), self.submit()), 15)
        self.assertEqual(first.id, second.id)
        self.assertEqual(await self.counts(), (1, 1, 1, 0))
        self.enqueue.assert_awaited_once()

    async def test_different_requests_concurrently_accept_only_one_input(self):
        results = await asyncio.wait_for(asyncio.gather(
            self.submit("request-a", dispatch_policy="reject"),
            self.submit("request-b", dispatch_policy="reject"),
            return_exceptions=True,
        ), 15)
        self.assertEqual(sum(isinstance(value, AgentRun) for value in results), 1)
        self.assertEqual(sum(isinstance(value, AgentRunConflictError) for value in results), 1)
        self.assertEqual(await self.counts(), (1, 1, 1, 0))
        self.enqueue.assert_awaited_once()

    async def test_same_request_across_threads_conflicts_without_duplicate_input(self):
        results = await asyncio.wait_for(asyncio.gather(
            self.submit(), self.submit(thread_id="thread-2"), return_exceptions=True,
        ), 15)
        errors = [value for value in results if isinstance(value, Exception)]
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], AgentRunConflictError)
        self.assertEqual(str(errors[0]), "request_id 已被其他请求使用")
        self.assertEqual(await self.counts(), (1, 1, 1, 0))

    async def test_existing_run_without_request_is_returned_without_writes(self):
        original = await self.add_blocking_run()
        self.model.side_effect = ValueError("model disabled")
        run = await self.submit("blocking-request")
        self.assertEqual(run.id, original.id)
        self.assertEqual(await self.counts(), (0, 0, 1, 0))
        self.enqueue.assert_not_awaited()

    async def test_request_ownership_checked_even_when_no_run_exists(self):
        await self.add_blocking_run()
        await self.submit(dispatch_policy="steer")
        with self.assertRaisesRegex(AgentRunConflictError, "其他请求"):
            await self.submit(thread_id="thread-2")
        self.assertEqual(await self.counts(), (1, 1, 1, 0))

    async def test_migration_roundtrip_preserves_runs_and_uses_reference_only_schema(self):
        run = await self.submit()
        async with self.engine.begin() as connection:
            columns = await connection.run_sync(lambda db: inspect(db).get_columns("agent_run_request"))
            self.assertEqual({column["name"] for column in columns}, {
                "request_id", "uid", "thread_id", "agent_id", "trigger_message_id", "created_at",
            "dispatch_policy", "status", "queue_seq",
            })
            await connection.run_sync(self.migrate_queue, "downgrade")
            await connection.run_sync(self.migrate_queue, "upgrade")
            self.assertEqual(await connection.scalar(select(AgentRunRequest.request_id)), "request-1")
            await connection.run_sync(self.migrate_queue, "downgrade")
            await connection.run_sync(self.migrate, "downgrade")
            self.assertEqual(await connection.scalar(select(AgentRun.id)), run.id)
            await connection.run_sync(self.migrate, "upgrade")
            await connection.run_sync(self.migrate_queue, "upgrade")
            self.assertEqual(await connection.scalar(select(func.count()).select_from(AgentRunRequest)), 0)
        self.assertEqual((await self.submit()).id, run.id)

    async def test_message_delete_cascades_to_request(self):
        await self.add_blocking_run()
        await self.submit(dispatch_policy="steer")
        async with self.sessions() as db:
            await db.execute(delete(Message))
            await db.commit()
        self.assertEqual(await self.counts(), (0, 0, 1, 0))

    async def test_conversation_delete_cascades_to_request(self):
        await self.submit()
        async with self.sessions() as db:
            await db.execute(delete(Conversation).where(Conversation.id == 1))
            await db.commit()
        self.assertEqual(await self.counts(), (0, 0, 0, 0))
