"""Agent Run 租约：认领、续租、释放与过期收敛。"""

import unittest
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.database.models import AgentRun, AgentRunAttempt, Conversation, Message, User
from src.database.repositories.agent_run_repository import (
    DEFAULT_RUN_LEASE_SECONDS,
    AgentRunRepository,
)


class LeaseTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        AgentRun.metadata.create_all(engine, tables=[
            User.__table__,
            Conversation.__table__,
            Message.__table__,
            AgentRun.__table__,
            AgentRunAttempt.__table__,
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

            async def scalar(_, statement):
                return self.db.scalar(statement)

            def add(_, instance):
                self.db.add(instance)

        self.repository = AgentRunRepository(AsyncSessionAdapter())

    def _reload(self) -> AgentRun:
        return self.db.execute(
            select(AgentRun).where(AgentRun.id == "run-1")
        ).scalar_one()

    async def test_claim_writes_a_lease_and_renew_extends_it(self):
        now = datetime.now(UTC)
        claimed = await self.repository.set_running(
            "run-1", worker_id="worker-a:1", lease_seconds=120, now=now,
        )
        self.assertIs(claimed, self.run)
        self.db.commit()
        self.assertEqual(now, self.run.heartbeat_at)
        self.assertEqual(now + timedelta(seconds=120), self.run.lease_expires_at)
        attempt = self.db.execute(
            select(AgentRunAttempt).where(AgentRunAttempt.run_id == "run-1")
        ).scalar_one()
        self.assertEqual("worker-a:1", attempt.worker_id)
        self.assertEqual(1, attempt.attempt_no)
        self.assertEqual("running", attempt.status)
        self.assertEqual(now, attempt.heartbeat_at.replace(tzinfo=UTC))
        self.assertEqual(now + timedelta(seconds=120), attempt.lease_expires_at.replace(tzinfo=UTC))
        self.assertIsNone(attempt.finished_at)

        later = now + timedelta(seconds=30)
        renewed = await self.repository.renew_lease(
            "run-1", worker_id="worker-a:1", lease_seconds=120, now=later,
        )
        self.assertTrue(renewed)
        self.db.commit()
        run = self._reload()
        self.assertEqual(later, run.heartbeat_at)
        self.assertEqual(later + timedelta(seconds=120), run.lease_expires_at)
        attempt = self.db.execute(
            select(AgentRunAttempt).where(AgentRunAttempt.run_id == "run-1")
        ).scalar_one()
        self.assertEqual(later, attempt.heartbeat_at.replace(tzinfo=UTC))
        self.assertEqual(later + timedelta(seconds=120), attempt.lease_expires_at.replace(tzinfo=UTC))

    async def test_other_owner_cannot_renew(self):
        now = datetime.now(UTC)
        await self.repository.set_running("run-1", worker_id="worker-a:1", now=now)
        self.db.commit()

        self.assertFalse(await self.repository.renew_lease(
            "run-1", worker_id="worker-b:1", now=now + timedelta(seconds=5),
        ))

    async def test_expired_lease_cannot_be_renewed(self):
        now = datetime.now(UTC)
        await self.repository.set_running(
            "run-1", worker_id="worker-a:1", lease_seconds=30, now=now,
        )
        self.db.commit()

        self.assertFalse(await self.repository.renew_lease(
            "run-1",
            worker_id="worker-a:1",
            lease_seconds=30,
            now=now + timedelta(seconds=31),
        ))

    async def test_reconcile_fails_expired_runs_and_cancels_cancel_requested(self):
        now = datetime.now(UTC)
        await self.repository.set_running(
            "run-1", worker_id="worker-a:1", lease_seconds=30, now=now,
        )
        self.run.agent_status = "cancel_requested"
        self.db.execute(Message.__table__.insert().values(
            conversation_id=1,
            agent_run_id="run-1",
            role="assistant",
            content="",
            message_type="model_audit",
            execution_status="running",
        ))
        self.db.commit()

        reconciled = await self.repository.reconcile_expired_leases(
            now=now + timedelta(seconds=31)
        )
        self.db.commit()

        self.assertEqual(["run-1"], [run.id for run in reconciled])
        run = self._reload()
        self.assertEqual("cancelled", run.agent_status)
        self.assertIsNone(run.worker_id)
        self.assertIsNone(run.lease_expires_at)
        self.assertIsNone(run.heartbeat_at)
        self.assertIsNotNone(run.finished_at)
        audit = self.db.execute(
            select(Message).where(Message.agent_run_id == "run-1")
        ).scalar_one()
        self.assertEqual("interrupted", audit.execution_status)
        self.assertIsNotNone(audit.finished_at)

    async def test_reconcile_marks_running_as_failed_when_lease_expires(self):
        now = datetime.now(UTC)
        await self.repository.set_running(
            "run-1", worker_id="worker-a:1", lease_seconds=30, now=now,
        )
        self.db.commit()

        await self.repository.reconcile_expired_leases(now=now + timedelta(seconds=31))
        self.db.commit()

        run = self._reload()
        self.assertEqual("failed", run.agent_status)
        self.assertEqual("LeaseExpired", run.error_type)
        self.assertIn("lease expired", run.error.lower())

    async def test_live_lease_is_left_alone(self):
        now = datetime.now(UTC)
        await self.repository.set_running(
            "run-1", worker_id="worker-a:1", lease_seconds=120, now=now,
        )
        self.db.commit()

        reconciled = await self.repository.reconcile_expired_leases(
            now=now + timedelta(seconds=30)
        )

        self.assertEqual([], reconciled)
        self.assertEqual("running", self._reload().agent_status)

    async def test_cancel_requested_stops_renewal(self):
        now = datetime.now(UTC)
        await self.repository.set_running(
            "run-1", worker_id="worker-a:1", lease_seconds=120, now=now,
        )
        await self.repository.request_cancel("run-1")
        self.db.commit()

        renewed = await self.repository.renew_lease(
            "run-1",
            worker_id="worker-a:1",
            lease_seconds=120,
            now=now + timedelta(seconds=30),
        )
        self.assertFalse(renewed)
        attempt = self.db.execute(
            select(AgentRunAttempt).where(AgentRunAttempt.run_id == "run-1")
        ).scalar_one()
        self.assertIsNone(attempt.finished_at)
        self.assertEqual(
            now + timedelta(seconds=120),
            attempt.lease_expires_at.replace(tzinfo=UTC),
        )

        _, changed = await self.repository.set_agent_terminal(
            "run-1", worker_id="worker-a:1", status="cancelled",
        )
        self.assertTrue(changed)
        self.db.commit()
        attempt = self.db.execute(
            select(AgentRunAttempt).where(AgentRunAttempt.run_id == "run-1")
        ).scalar_one()
        self.assertEqual("cancelled", attempt.status)

    async def test_check_run_stopped_uses_attempt_owner_and_lease(self):
        now = datetime.now(UTC)
        await self.repository.set_running(
            "run-1", worker_id="worker-a:1", lease_seconds=30, now=now,
        )
        self.db.commit()

        live = await self.repository.check_run_stopped(
            "run-1", worker_id="worker-a:1", now=now + timedelta(seconds=5),
        )
        self.assertFalse(live.stopped)
        self.assertEqual("worker-a:1", self._reload().worker_id)

        other_owner = await self.repository.check_run_stopped(
            "run-1", worker_id="worker-b:1", now=now + timedelta(seconds=5),
        )
        self.assertTrue(other_owner.stopped)
        self.assertEqual("owner_mismatch", other_owner.reason)

        expired = await self.repository.check_run_stopped(
            "run-1", worker_id="worker-a:1", now=now + timedelta(seconds=31),
        )
        self.assertTrue(expired.stopped)
        self.assertEqual("lease_expired", expired.reason)

        await self.repository.request_cancel("run-1")
        self.db.commit()
        cancelled = await self.repository.check_run_stopped(
            "run-1", worker_id="worker-a:1", now=now + timedelta(seconds=5),
        )
        self.assertTrue(cancelled.stopped)
        self.assertEqual("cancel_requested", cancelled.reason)

        _, changed = await self.repository.set_agent_terminal(
            "run-1", worker_id="worker-a:1", status="cancelled",
        )
        self.assertTrue(changed)
        self.db.commit()
        terminal = await self.repository.check_run_stopped(
            "run-1", worker_id="worker-a:1", now=now + timedelta(seconds=5),
        )
        self.assertTrue(terminal.stopped)
        self.assertEqual("terminal", terminal.reason)

    async def test_terminal_status_releases_the_lease(self):
        now = datetime.now(UTC)
        await self.repository.set_running(
            "run-1", worker_id="worker-a:1", lease_seconds=DEFAULT_RUN_LEASE_SECONDS, now=now,
        )
        self.db.commit()

        _, changed = await self.repository.set_agent_terminal(
            "run-1", worker_id="worker-a:1", status="completed",
        )
        self.db.commit()

        self.assertTrue(changed)
        run = self._reload()
        self.assertEqual("completed", run.agent_status)
        self.assertIsNone(run.heartbeat_at)
        self.assertIsNone(run.lease_expires_at)
        attempt = self.db.execute(
            select(AgentRunAttempt).where(AgentRunAttempt.run_id == "run-1")
        ).scalar_one()
        self.assertEqual("completed", attempt.status)
        self.assertIsNotNone(attempt.finished_at)
        self.assertEqual([], await self.repository.reconcile_expired_leases(
            now=now + timedelta(seconds=3600)
        ))
