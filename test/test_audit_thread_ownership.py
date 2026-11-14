"""消息审计只能写入当前用户拥有的 Thread。"""

import unittest
from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.database.models import AgentRun, AgentRunExecution, Conversation, Message
from src.database.repositories.model_message_audit_repository import (
    ModelMessageAuditRepository,
)


class AsyncSessionAdapter:
    def __init__(self, session: Session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)

    async def flush(self) -> None:
        self.session.flush()

    async def refresh(self, value) -> None:
        self.session.refresh(value)

    def add(self, value) -> None:
        self.session.add(value)


class AuditThreadOwnershipTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        Conversation.__table__.create(self.engine)
        AgentRun.__table__.create(self.engine)
        Message.__table__.create(self.engine)
        AgentRunExecution.__table__.create(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)
        self.addCleanup(self.session.close)
        self.session.add(
            Conversation(
                id=1,
                uid="user-1",
                thread_id="thread-1",
                agent_id="agent",
                title="Thread",
                conversation_metadata={},
            )
        )
        self.session.add(
            AgentRun(
                id="run-1",
                uid="user-1",
                conversation_id=1,
                thread_id="thread-1",
                agent_id="agent",
                agent_status="running",
                worker_id="worker-1",
                request_id="request-1",
            )
        )
        self.session.commit()
        self.repository = ModelMessageAuditRepository(
            AsyncSessionAdapter(self.session)
        )

    async def test_foreign_user_cannot_audit_thread(self) -> None:
        with self.assertRaisesRegex(ValueError, "当前用户"):
            await self._start(uid="user-2")
        messages = self.session.execute(select(Message)).scalars().all()
        self.assertEqual(messages, [])

    async def test_owner_can_audit_thread(self) -> None:
        message, created = await self._start(uid="user-1")
        self.assertTrue(created)
        self.assertEqual(message.conversation_id, 1)

    async def test_mismatched_thread_cannot_be_audited(self) -> None:
        with self.assertRaisesRegex(ValueError, "同一 thread"):
            await self._start(uid="user-1", thread_id="thread-2")
        messages = self.session.execute(select(Message)).scalars().all()
        self.assertEqual(messages, [])

    async def _start(self, *, uid: str, thread_id: str = "thread-1"):
        return await self.repository.start(
            uid=uid,
            run_id="run-1",
            request_id="request-1",
            thread_id=thread_id,
            worker_id="worker-1",
            operation_id="model-operation-1",
            sequence=1,
            started_at=datetime.now(UTC),
        )
