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

from server.service import agent_run_service, attachment_service
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
    AgentRunRequestRepository,
    ConversationRepository,
)

MIGRATION_PATH = Path(__file__).resolve().parents[1] / "migrate/versions/0028_agent_run_request.py"
spec = importlib.util.spec_from_file_location("run_request_migration", MIGRATION_PATH)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class AgentRunRequestRepositoryTest(unittest.IsolatedAsyncioTestCase):
    """用 SQLite 验证实际 SQL 与迁移；PostgreSQL 行锁竞争由下方集成测试验证。"""

    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        with self.engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            Base.metadata.create_all(connection, tables=[
                model.__table__ for model in (Project, Conversation, Message, AgentRun)
            ])
            self.migrate(connection, "upgrade")
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

    @staticmethod
    def migrate(connection, action):
        with patch.object(migration, "op", Operations(MigrationContext.configure(connection))):
            getattr(migration, action)()

    async def create_request(self):
        return await self.repository.create_request(
            request_id="request-1", uid="user-1", conversation_id=1, thread_id="thread-1",
            agent_id="leader", trigger_message_id=1,
        )

    async def test_reads_request_and_current_conversation_configuration(self):
        await self.create_request()
        self.db.commit()
        self.db.execute(update(Conversation).values(conversation_metadata={"model": "test/changed"}))
        self.db.commit()
        request = await self.repository.get_by_request_id("request-1")
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
            "request_id", "uid", "conversation_id", "thread_id", "agent_id", "trigger_message_id", "created_at",
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
        self.assertIsNotNone(await self.repository.get_by_request_id("request-1"))
        self.assertIsNone(self.db.get(Message, 1).agent_run_id)
        self.assertIsNone(self.db.get(AgentRun, "run-1"))

    async def test_repository_does_not_commit_and_message_delete_cascades(self):
        await self.create_request()
        self.db.rollback()
        self.assertIsNone(await self.repository.get_by_request_id("request-1"))
        await self.create_request()
        self.db.commit()
        self.db.execute(delete(Message))
        self.db.commit()
        self.assertIsNone(await self.repository.get_by_request_id("request-1"))

    async def test_migration_roundtrip_preserves_existing_run(self):
        await self.create_request()
        await AgentRunRepository(self.session).create_run(
            run_id="run-1", uid="user-1", conversation_id=1, thread_id="thread-1",
            agent_slug="leader", request_id="request-1", trigger_message_id=1,
        )
        self.db.commit()
        with self.engine.begin() as connection:
            self.migrate(connection, "downgrade")
            self.assertFalse(inspect(connection).has_table("agent_run_request"))
            self.assertEqual(connection.scalar(select(AgentRun.id)), "run-1")
            self.migrate(connection, "upgrade")
            self.assertTrue(inspect(connection).has_table("agent_run_request"))
        self.assertIsNone(await self.repository.get_by_request_id("request-1"))


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
            patch.object(agent_run_service, "enqueue_agent_run", self.enqueue),
            patch.object(agent_run_service, "resolve_runtime_model", self.model),
            patch.object(attachment_service, "get_storage", return_value=self.storage),
            patch.object(agent_run_service.logger, "exception"),
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

    async def submit(self, request_id="request-1", *, db=None, **changes):
        values = {
            "current_user": SimpleNamespace(id=7, uid="user-1"),
            "query": "原始输入", "agent_id": "leader", "thread_id": "thread-1",
            "request_metadata": {"type": "chat", "request_id": request_id},
            "image_content": "https://example.test/input.png",
        }
        values.update(changes)
        if db is not None:
            return await agent_run_service.create_agent_run_service(db=db, **values)
        async with self.sessions() as session:
            return await agent_run_service.create_agent_run_service(db=session, **values)

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

    async def test_busy_preserves_request_then_retry_uses_original_message_and_current_model(self):
        await self.add_blocking_run()
        with self.assertRaisesRegex(agent_run_service.AgentRunConflictError, "正在执行"):
            await self.submit(request_metadata={"type": "chat", "request_id": "request-1", "attachment_file_ids": [self.file_id]})
        self.assertEqual(await self.counts(), (1, 1, 1, 1))
        self.enqueue.assert_not_awaited()
        async with self.sessions() as db:
            message = await db.scalar(select(Message))
            original_message_id = message.id
            self.assertIsNone(message.agent_run_id)
            await db.execute(update(AgentRun).values(agent_status="completed"))
            await db.execute(update(Conversation).where(Conversation.id == 1).values(
                conversation_metadata={"model": "test/changed", "workspace": "new"},
            ))
            await db.commit()
        run = await self.submit(
            query="重发的新正文", image_content=None,
            request_metadata={"type": "chat", "request_id": "request-1", "model": "test/ignored"},
        )
        self.assertEqual(run.trigger_message_id, original_message_id)
        self.assertEqual(run.run_metadata["model"], "test/changed")
        self.assertEqual(run.run_metadata["workspace"], "new")
        async with self.sessions() as db:
            message = await db.get(Message, original_message_id)
            self.assertEqual(message.content, "原始输入")
            self.assertEqual(message.agent_run_id, run.id)
            request = await AgentRunRequestRepository(db).get_by_request_id("request-1")
            self.assertEqual(request.trigger_message_id, original_message_id)
            self.assertEqual((await db.get(Conversation, 1)).conversation_metadata["model"], "test/changed")
        self.assertEqual(await self.counts(), (1, 1, 2, 1))
        self.storage.acopy_file.assert_awaited_once()

    async def test_pending_interaction_preserves_input_and_does_not_enqueue(self):
        await self.add_blocking_run("interrupted")
        with self.assertRaisesRegex(agent_run_service.AgentRunConflictError, "待回答"):
            await self.submit()
        self.assertEqual(await self.counts(), (1, 1, 1, 0))
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

    async def test_run_commit_failure_keeps_received_input_and_allows_retry(self):
        async with self.sessions() as db:
            commit = db.commit
            count = 0

            async def fail_second_commit():
                nonlocal count
                count += 1
                if count == 2:
                    raise RuntimeError("run commit failed")
                await commit()

            with patch.object(db, "commit", fail_second_commit):
                with self.assertRaisesRegex(RuntimeError, "run commit failed"):
                    await self.submit(db=db, request_metadata={"type": "chat", "request_id": "request-1", "attachment_file_ids": [self.file_id]})
        self.assertEqual(await self.counts(), (1, 1, 0, 1))
        async with self.sessions() as db:
            self.assertIsNone((await db.scalar(select(Message))).agent_run_id)
        self.enqueue.assert_not_awaited()
        self.storage.adelete_file.assert_awaited_once_with(attachment_service.ATTACHMENT_BUCKET_NAME, self.source)
        await self.submit()
        self.assertEqual(await self.counts(), (1, 1, 1, 1))

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

    async def test_different_requests_concurrently_keep_both_inputs_and_only_one_active_run(self):
        results = await asyncio.wait_for(asyncio.gather(
            self.submit("request-a"), self.submit("request-b"), return_exceptions=True,
        ), 15)
        self.assertEqual(sum(isinstance(value, AgentRun) for value in results), 1)
        self.assertEqual(sum(isinstance(value, agent_run_service.AgentRunConflictError) for value in results), 1)
        self.assertEqual(await self.counts(), (2, 2, 1, 0))
        self.enqueue.assert_awaited_once()

    async def test_same_request_across_threads_conflicts_without_duplicate_input(self):
        results = await asyncio.wait_for(asyncio.gather(
            self.submit(), self.submit(thread_id="thread-2"), return_exceptions=True,
        ), 15)
        errors = [value for value in results if isinstance(value, Exception)]
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], agent_run_service.AgentRunConflictError)
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
        with self.assertRaises(agent_run_service.AgentRunConflictError):
            await self.submit()
        with self.assertRaisesRegex(agent_run_service.AgentRunConflictError, "其他请求"):
            await self.submit(thread_id="thread-2")
        self.assertEqual(await self.counts(), (1, 1, 1, 0))

    async def test_migration_roundtrip_preserves_runs_and_uses_reference_only_schema(self):
        run = await self.submit()
        async with self.engine.begin() as connection:
            columns = await connection.run_sync(lambda db: inspect(db).get_columns("agent_run_request"))
            self.assertEqual({column["name"] for column in columns}, {
                "request_id", "uid", "conversation_id", "thread_id", "agent_id", "trigger_message_id", "created_at",
            })
            await connection.run_sync(self.migrate, "downgrade")
            self.assertEqual(await connection.scalar(select(AgentRun.id)), run.id)
            await connection.run_sync(self.migrate, "upgrade")
            self.assertEqual(await connection.scalar(select(func.count()).select_from(AgentRunRequest)), 0)
        self.assertEqual((await self.submit()).id, run.id)

    async def test_message_delete_cascades_to_request(self):
        await self.add_blocking_run()
        with self.assertRaises(agent_run_service.AgentRunConflictError):
            await self.submit()
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
