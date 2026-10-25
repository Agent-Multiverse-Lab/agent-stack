"""Agent Run 租约：认领、续租、释放与过期收敛。"""

import unittest
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.database.models import AgentRun, Conversation, Message, User
from src.database.repositories.agent_run_repository import (
    AgentRunRepository,
    DEFAULT_RUN_LEASE_SECONDS,
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

        later = now + timedelta(seconds=30)
        renewed = await self.repository.renew_lease(
            "run-1", worker_id="worker-a:1", lease_seconds=120, now=later,
        )
        self.assertTrue(renewed)
        self.db.commit()
        run = self._reload()
        self.assertEqual(later, run.heartbeat_at)
        self.assertEqual(later + timedelta(seconds=120), run.lease_expires_at)

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
        self.assertEqual([], await self.repository.reconcile_expired_leases(
            now=now + timedelta(seconds=3600)
        ))
