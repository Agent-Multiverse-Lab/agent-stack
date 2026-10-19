"""Agent Run 终态写入测试。"""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.database.models import AgentRun, Conversation, Message, User
from src.database.repositories.agent_run_repository import AgentRunRepository


class FakeSession:
    def __init__(self) -> None:
        self.flush_count = 0

    async def flush(self) -> None:
        self.flush_count += 1


class AgentRunTerminalTest(unittest.IsolatedAsyncioTestCase):
    async def test_set_agent_terminal_persists_interrupt_payload(self) -> None:
        session = FakeSession()
        run = SimpleNamespace(
            agent_status="running",
            worker_id="owner-1",
            run_metadata={"model": "test-model"},
            finished_at=None,
        )
        repository = AgentRunRepository(session)  # type: ignore[arg-type]
        repository._lock_update = AsyncMock(return_value=run)
        payload = {
            "kind": "ask_user",
            "question": "请选择数据库",
            "options": ["PostgreSQL", "MySQL"],
        }

        # FIXEME: interrupted 复用统一终态写入并保留已有 Run metadata。
        terminal_message = json.dumps(payload, ensure_ascii=False)
        result, changed = await repository.set_agent_terminal(
            "run-1", worker_id="owner-1",
            status="interrupted",
            error=terminal_message,
            error_type="ask_user",
        )

        self.assertIs(run, result)
        self.assertTrue(changed)
        self.assertEqual("interrupted", run.agent_status)
        self.assertEqual("test-model", run.run_metadata["model"])
        self.assertEqual(payload, run.run_metadata["interrupt"])
        self.assertEqual(terminal_message, run.error)
        self.assertEqual("ask_user", run.error_type)
        self.assertIsNotNone(run.finished_at)
        self.assertEqual(1, session.flush_count)

    async def test_writes_completed_failed_and_cancelled(self) -> None:
        cases = (
            ("running", "completed", None, None),
            ("running", "failed", "boom", "RuntimeError"),
            ("cancel_requested", "cancelled", None, None),
        )

        for current_status, status, error, error_type in cases:
            with self.subTest(status=status):
                session = FakeSession()
                run = SimpleNamespace(
                    agent_status=current_status,
                    worker_id="owner-1",
                    finished_at=None,
                    error="old error",
                    error_type="OldError",
                )
                repository = AgentRunRepository(session)  # type: ignore[arg-type]
                repository._lock_update = AsyncMock(return_value=run)

                result, changed = await repository.set_agent_terminal(
                    "run-1", worker_id="owner-1",
                    status=status,
                    error=error,
                    error_type=error_type,
                )

                self.assertIs(run, result)
                self.assertTrue(changed)
                self.assertEqual(status, run.agent_status)
                self.assertEqual(error, run.error)
                self.assertEqual(error_type, run.error_type)
                self.assertIsNotNone(run.finished_at)
                self.assertEqual(1, session.flush_count)

    async def test_preserves_existing_terminal_or_interrupted_status(self) -> None:
        cases = (
            ("completed", "failed"),
            ("interrupted", "failed"),
        )

        for current_status, status in cases:
            with self.subTest(current_status=current_status, status=status):
                session = FakeSession()
                run = SimpleNamespace(
                    agent_status=current_status,
                    worker_id="owner-1",
                    finished_at=None,
                    error=None,
                    error_type=None,
                )
                repository = AgentRunRepository(session)  # type: ignore[arg-type]
                repository._lock_update = AsyncMock(return_value=run)

                result, changed = await repository.set_agent_terminal(
                    "run-1", worker_id="owner-1",
                    status=status,
                )

                self.assertIs(run, result)
                self.assertFalse(changed)
                self.assertEqual(current_status, run.agent_status)
                self.assertIsNone(run.finished_at)
                self.assertEqual(0, session.flush_count)

    async def test_rejects_non_terminal_status(self) -> None:
        session = FakeSession()
        repository = AgentRunRepository(session)  # type: ignore[arg-type]
        repository._lock_update = AsyncMock()

        with self.assertRaisesRegex(ValueError, "running"):
            await repository.set_agent_terminal("run-1", worker_id="owner-1", status="running")

        repository._lock_update.assert_not_awaited()
        self.assertEqual(0, session.flush_count)


class AgentRunOwnershipTest(unittest.IsolatedAsyncioTestCase):
    """使用真实 SQLite 行验证归属转换；PostgreSQL 行锁竞争需集成验证。"""

    def setUp(self):
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        AgentRun.metadata.create_all(engine, tables=[
            User.__table__, Conversation.__table__, Message.__table__, AgentRun.__table__,
        ])
        self.db = Session(engine, expire_on_commit=False)
        self.addCleanup(self.db.close)
        self.db.execute(User.__table__.insert().values(
            uid="user-1", email="user@example.test", password_hash="unused",
        ))
        self.db.execute(Conversation.__table__.insert().values(
            id=1, uid="user-1", thread_id="thread-1", agent_id="agent", title="test",
        ))
        self.run = AgentRun(
            id="run-1", uid="user-1", conversation_id=1,
            thread_id="thread-1", agent_id="agent", agent_status="pending",
        )
        self.db.add(self.run)
        self.db.commit()

        class AsyncSessionAdapter:
            async def execute(_, statement):
                return self.db.execute(statement)

            async def flush(_):
                self.db.flush()

        self.repository = AgentRunRepository(AsyncSessionAdapter())

    async def test_only_one_attempt_claims_and_finishes_the_run(self):
        claimed = await self.repository.set_running("run-1", worker_id="worker-a:1")
        self.assertIs(claimed, self.run)
        self.db.commit()
        for token in ("worker-b:1", "worker-a:1", "worker-a:2"):
            self.assertIsNone(await self.repository.set_running("run-1", worker_id=token))
        _, changed = await self.repository.set_agent_terminal(
            "run-1", worker_id="worker-b:1", status="failed",
        )
        self.assertFalse(changed)
        self.assertEqual(self.run.agent_status, "running")
        _, changed = await self.repository.set_agent_terminal(
            "run-1", worker_id="worker-a:1", status="completed",
        )
        self.assertTrue(changed)
        self.assertEqual(self.run.agent_status, "completed")

    async def test_retry_reclaims_with_new_token_and_rejects_old_writes(self):
        await self.repository.set_running("run-1", worker_id="worker-a:1")
        self.assertFalse(await self.repository.release_for_retry("run-1", worker_id="worker-b:1"))
        self.assertTrue(await self.repository.release_for_retry("run-1", worker_id="worker-a:1"))
        self.assertIsNone(self.run.worker_id)
        self.assertEqual(self.run.agent_status, "pending")
        self.db.commit()
        await self.repository.set_running("run-1", worker_id="worker-a:2")
        self.db.commit()

        _, changed = await self.repository.set_agent_terminal(
            "run-1", worker_id="worker-a:1", status="failed",
        )
        self.assertFalse(changed)
        self.assertFalse(await self.repository.release_for_retry("run-1", worker_id="worker-a:1"))
        with self.assertRaisesRegex(RuntimeError, "归属不匹配"):
            await self.repository.set_output_message(
                run_id="run-1", worker_id="worker-a:1", output_message_id=9,
            )
        self.assertIsNone(self.run.output_message_id)
        await self.repository.set_output_message(
            run_id="run-1", worker_id="worker-a:2", output_message_id=9,
        )
        self.assertEqual(self.run.output_message_id, 9)

    async def test_cancel_keeps_owner_and_only_owner_finalizes(self):
        await self.repository.set_running("run-1", worker_id="worker-a:1")
        await self.repository.request_cancel("run-1")
        self.assertEqual(self.run.worker_id, "worker-a:1")
        self.assertIsNone(await self.repository.set_running("run-1", worker_id="worker-b:1"))
        for token in (None, "worker-b:1"):
            _, changed = await self.repository.set_agent_terminal(
                "run-1", worker_id=token, status="cancelled",
            )
            self.assertFalse(changed)
        _, changed = await self.repository.set_agent_terminal(
            "run-1", worker_id="worker-a:1", status="cancelled",
        )
        self.assertTrue(changed)

    async def test_cancel_before_claim_and_retry_preserve_cancel_intent(self):
        await self.repository.request_cancel("run-1")
        await self.repository.set_running("run-1", worker_id="worker-a:1")
        self.assertEqual(self.run.agent_status, "cancel_requested")
        self.assertTrue(await self.repository.release_for_retry("run-1", worker_id="worker-a:1"))
        await self.repository.set_running("run-1", worker_id="worker-b:1")
        self.assertEqual(self.run.agent_status, "cancel_requested")
        self.assertEqual(self.run.worker_id, "worker-b:1")

    async def test_queue_failure_without_token_cannot_modify_claimed_run(self):
        await self.repository.set_running("run-1", worker_id="worker-a:1")
        _, changed = await self.repository.set_agent_terminal("run-1", status="failed")
        self.assertFalse(changed)
        self.assertEqual(self.run.agent_status, "running")

    async def test_queue_failure_can_finalize_unclaimed_run(self):
        _, changed = await self.repository.set_agent_terminal("run-1", status="failed")
        self.assertTrue(changed)
        self.assertEqual(self.run.agent_status, "failed")


if __name__ == "__main__":
    unittest.main()
