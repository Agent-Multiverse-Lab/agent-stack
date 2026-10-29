"""消息审计：Model/Tool 生命周期、单调耗时与普通历史隔离。"""

import json
import unittest
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest import mock

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from server.service import model_message_audit_service, tool_message_audit_service
from server.service.model_message_audit_service import ModelMessageAuditCollector
from server.service.tool_message_audit_service import ToolMessageAuditCollector
from src.database.models import (
    MODEL_AUDIT_MESSAGE_TYPE,
    TOOL_AUDIT_MESSAGE_TYPE,
    AgentRun,
    AgentRunAttempt,
    Conversation,
    Message,
    User,
)
from src.database.repositories.agent_run_repository import AgentRunRepository
from src.database.repositories.conversation_repository import ConversationRepository
from src.database.repositories.model_message_audit_repository import (
    ModelMessageAuditRepository,
)
from src.database.repositories.tool_message_audit_repository import (
    ToolMessageAuditRepository,
)


def _v3_metadata(seq: int, timestamp: int, *, namespace=("model:abc",)):
    return {
        "run_id": "langchain-model-run-1",
        "stream_event": {
            "method": "messages",
            "namespace": list(namespace),
            "seq": seq,
            "timestamp": timestamp,
        },
    }


class ModelAuditCollectorTest(unittest.IsolatedAsyncioTestCase):
    async def test_collector_projects_real_v3_message_lifecycle(self):
        """真实 v3 start/delta/finish 形状必须保留来源键、顺序、时间和 usage。"""
        calls: list[tuple[str, dict]] = []

        @asynccontextmanager
        async def session_context():
            yield object()

        class FakeRepository:
            def __init__(self, _db):
                pass

            async def start(self, **kwargs):
                calls.append(("start", kwargs))
                return SimpleNamespace(id=1), True

            async def finish(self, **kwargs):
                calls.append(("finish", kwargs))
                return SimpleNamespace(id=1)

        monotonic_values = iter([100.0, 100.321])
        collector = ModelMessageAuditCollector(
            run_id="run-1",
            request_id="request-1",
            thread_id="thread-1",
            worker_id="worker-1",
        )
        metadata = _v3_metadata(7, 1_777_000_123_456)
        with mock.patch.object(
            model_message_audit_service.postgres_manager,
            "get_async_session_context",
            session_context,
        ), mock.patch.object(
            model_message_audit_service, "ModelMessageAuditRepository", FakeRepository
        ), mock.patch.object(
            model_message_audit_service,
            "monotonic",
            lambda: next(monotonic_values),
        ):
            await collector.consume(
                {
                    "event": "message-start",
                    "role": "ai",
                    "id": "lc_run--model-message-1",
                    "metadata": {"provider": "openai"},
                },
                metadata,
            )
            await collector.consume(
                {
                    "event": "content-block-delta",
                    "index": 0,
                    "delta": {"type": "text-delta", "text": "hello"},
                },
                metadata,
            )
            await collector.consume(
                {
                    "event": "content-block-finish",
                    "index": 0,
                    "content": {"type": "text", "text": "hello"},
                },
                metadata,
            )
            await collector.consume(
                {
                    "event": "message-finish",
                    "usage": {"input_tokens": 8, "output_tokens": 2, "total_tokens": 10},
                    "metadata": {"model_name": "deterministic-chat"},
                },
                _v3_metadata(8, 1_777_000_123_789),
            )

        self.assertEqual([name for name, _ in calls], ["start", "finish"])
        start = calls[0][1]
        self.assertEqual(start["operation_id"], "lc_run--model-message-1")
        self.assertEqual(start["sequence"], 7)
        self.assertEqual(start["metadata"]["model_run_id"], "langchain-model-run-1")
        self.assertEqual(start["started_at"], datetime.fromtimestamp(1777000123.456, UTC))

        finish = calls[1][1]
        self.assertEqual(finish["content"], "hello")
        self.assertEqual(finish["duration_ms"], 321)
        self.assertEqual(
            finish["usage"],
            {"input_tokens": 8, "output_tokens": 2, "total_tokens": 10},
        )
        self.assertEqual(finish["metadata"]["finished_sequence"], 8)
        self.assertEqual(
            finish["metadata"]["content"], [{"type": "text", "text": "hello"}]
        )

    async def test_lifecycle_without_seq_is_rejected(self):
        collector = ModelMessageAuditCollector(
            run_id="run-1",
            request_id="request-1",
            thread_id="thread-1",
            worker_id="worker-1",
        )
        with self.assertRaises(ValueError):
            await collector.consume(
                {"event": "message-start", "id": "lc_run--1"},
                {"stream_event": {"namespace": [], "timestamp": 1}},
            )


class ToolAuditCollectorTest(unittest.IsolatedAsyncioTestCase):
    async def test_collector_projects_tool_lifecycle(self):
        calls: list[tuple[str, dict]] = []

        @asynccontextmanager
        async def session_context():
            yield object()

        class FakeRepository:
            def __init__(self, _db):
                pass

            async def start(self, **kwargs):
                calls.append(("start", kwargs))
                return SimpleNamespace(id=1), True

            async def complete(self, **kwargs):
                calls.append(("complete", kwargs))
                return SimpleNamespace(id=1)

            async def fail(self, **kwargs):
                calls.append(("fail", kwargs))
                return SimpleNamespace(id=1)

        monotonic_values = iter([50.0, 50.25])
        collector = ToolMessageAuditCollector(
            run_id="run-1",
            request_id="request-1",
            thread_id="thread-1",
            worker_id="worker-1",
        )
        start_event = {
            "method": "tools",
            "namespace": [],
            "seq": 3,
            "timestamp": 1_777_000_200_000,
            "data": {
                "event": "tool-started",
                "tool_call_id": "call-1",
                "tool_name": "calculator",
                "input": {"a": 1},
            },
        }
        finish_event = {
            "method": "tools",
            "namespace": [],
            "seq": 4,
            "timestamp": 1_777_000_200_400,
            "data": {
                "event": "tool-finished",
                "tool_call_id": "call-1",
                "output": {"content": "3"},
            },
        }
        with mock.patch.object(
            tool_message_audit_service.postgres_manager,
            "get_async_session_context",
            session_context,
        ), mock.patch.object(
            tool_message_audit_service, "ToolMessageAuditRepository", FakeRepository
        ), mock.patch.object(
            tool_message_audit_service, "monotonic", lambda: next(monotonic_values)
        ):
            await collector.consume(start_event)
            await collector.consume(finish_event)

        self.assertEqual([name for name, _ in calls], ["start", "complete"])
        self.assertEqual(calls[0][1]["sequence"], 3)
        self.assertEqual(calls[0][1]["tool_input"], {"a": 1})
        self.assertEqual(calls[1][1]["content"], "3")
        self.assertEqual(calls[1][1]["duration_ms"], 250)
        self.assertEqual(calls[1][1]["finished_sequence"], 4)

    async def test_non_tools_event_is_ignored(self):
        collector = ToolMessageAuditCollector(
            run_id="run-1",
            request_id="request-1",
            thread_id="thread-1",
            worker_id="worker-1",
        )
        await collector.consume({"method": "messages", "data": {}})


class _RecordingCollector:
    """记录被审计器消费的参数，用于验证流式分发边界。"""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def consume(self, *args) -> None:
        self.calls.append(args)


async def _collect_chunks(
    events,
    *,
    model_audit=None,
    tool_audit=None,
) -> list[dict]:
    from server.service.thread_service import _stream_agent_event_chunks

    async def source():
        for event in events:
            yield event

    chunks = []
    async for chunk in _stream_agent_event_chunks(
        stream_events=source(),
        thread_id="thread-1",
        make_event=lambda status=None, content=None, **kwargs: json.dumps(
            {"status": status, "content": content}
        ).encode(),
        accumulated_msg=[],
        model_audit=model_audit,
        tool_audit=tool_audit,
    ):
        chunks.append(json.loads(chunk))
    return chunks


class StreamAuditWiringTest(unittest.IsolatedAsyncioTestCase):
    async def test_model_lifecycle_needs_complete_envelope(self):
        model_audit = _RecordingCollector()
        chunks = await _collect_chunks(
            [
                (
                    "messages",
                    (
                        {
                            "event": "content-block-delta",
                            "index": 0,
                            "delta": {"type": "text-delta", "text": "a"},
                        },
                        {"run_id": "model-run-1"},
                    ),
                ),
                (
                    "messages",
                    (
                        {
                            "event": "content-block-delta",
                            "index": 0,
                            "delta": {"type": "text-delta", "text": "b"},
                        },
                        _v3_metadata(7, 1_777_000_123_456),
                    ),
                ),
            ],
            model_audit=model_audit,
        )
        self.assertEqual(len(model_audit.calls), 1)
        self.assertEqual(model_audit.calls[0][0]["delta"]["text"], "b")
        self.assertEqual([chunk["content"] for chunk in chunks], ["a", "b"])

    async def test_tool_lifecycle_needs_protocol_seq(self):
        tool_audit = _RecordingCollector()
        await _collect_chunks(
            [
                (
                    "agent_execute_event",
                    {
                        "method": "tools",
                        "data": {"event": "tool-started", "tool_call_id": "call-1"},
                        "stream_methods": "tools",
                    },
                ),
                (
                    "agent_execute_event",
                    {
                        "method": "tools",
                        "seq": 3,
                        "timestamp": 1_777_000_200_000,
                        "data": {"event": "tool-started", "tool_call_id": "call-2"},
                        "stream_methods": "tools",
                    },
                ),
            ],
            tool_audit=tool_audit,
        )
        self.assertEqual(len(tool_audit.calls), 1)
        self.assertEqual(tool_audit.calls[0][0]["data"]["tool_call_id"], "call-2")

    async def test_without_collectors_stream_still_yields_chunks(self):
        chunks = await _collect_chunks(
            [
                ("values", {"todos": []}),
                (
                    "messages",
                    (
                        {
                            "event": "content-block-delta",
                            "index": 0,
                            "delta": {"type": "text-delta", "text": "OK"},
                        },
                        _v3_metadata(8, 1_777_000_123_789),
                    ),
                ),
            ]
        )
        self.assertEqual([chunk["status"] for chunk in chunks], ["agent_state", "loading"])
        self.assertEqual(chunks[1]["content"], "OK")


class _AsyncSessionAdapter:
    """把同步 Session 适配成仓储期望的 AsyncSession 最小接口。"""

    def __init__(self, session: Session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)

    async def flush(self):
        self.session.flush()

    def add(self, instance):
        self.session.add(instance)

    async def refresh(self, instance):
        self.session.refresh(instance)


class AuditRepositoryTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        AgentRun.metadata.create_all(
            engine,
            tables=[
                User.__table__,
                Conversation.__table__,
                Message.__table__,
                AgentRun.__table__,
                AgentRunAttempt.__table__,
            ],
        )
        self.db = Session(engine, expire_on_commit=False)
        self.addCleanup(self.db.close)
        self.db.execute(
            User.__table__.insert().values(
                uid="user-1", email="user@example.test", password_hash="unused"
            )
        )
        self.db.execute(
            Conversation.__table__.insert().values(
                id=1, uid="user-1", thread_id="thread-1", agent_id="agent", title="t"
            )
        )
        self.db.add(
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
        self.db.commit()
        self.session = _AsyncSessionAdapter(self.db)

    def _messages(self, message_type: str | None = None):
        statement = select(Message).where(Message.agent_run_id == "run-1")
        if message_type is not None:
            statement = statement.where(Message.message_type == message_type)
        return list(self.db.execute(statement).scalars().all())

    async def _start_model(self, sequence: int = 7):
        return await ModelMessageAuditRepository(self.session).start(
            run_id="run-1",
            request_id="request-1",
            thread_id="thread-1",
            worker_id="worker-1",
            operation_id="lc_run--1",
            sequence=sequence,
            started_at=datetime.now(UTC),
            metadata={"audit_kind": "model"},
        )

    async def test_model_start_is_running_and_finish_records_duration(self):
        message, created = await self._start_model()
        self.db.commit()
        self.assertTrue(created)
        self.assertEqual(message.message_type, MODEL_AUDIT_MESSAGE_TYPE)
        self.assertEqual(message.execution_status, "running")
        self.assertEqual(message.sequence, 7)

        await ModelMessageAuditRepository(self.session).finish(
            run_id="run-1",
            request_id="request-1",
            thread_id="thread-1",
            worker_id="worker-1",
            operation_id="lc_run--1",
            content="hello",
            finished_at=datetime.now(UTC),
            duration_ms=321,
            usage={"total_tokens": 10},
            metadata={"finished_sequence": 8},
        )
        self.db.commit()
        row = self._messages(MODEL_AUDIT_MESSAGE_TYPE)[0]
        self.assertEqual(row.execution_status, "completed")
        self.assertEqual(row.content, "hello")
        self.assertEqual(row.duration_ms, 321)
        self.assertEqual(row.usage, {"total_tokens": 10})
        self.assertEqual(row.msg_metadata["finished_sequence"], 8)

    async def test_duplicate_start_is_idempotent_but_sequence_conflict_fails(self):
        await self._start_model()
        self.db.commit()
        _again, created = await self._start_model()
        self.db.commit()
        self.assertFalse(created)
        with self.assertRaises(ValueError):
            await self._start_model(sequence=9)

    async def test_different_finish_result_cannot_overwrite_completed_row(self):
        await self._start_model()
        self.db.commit()
        repository = ModelMessageAuditRepository(self.session)
        kwargs = dict(
            run_id="run-1",
            request_id="request-1",
            thread_id="thread-1",
            worker_id="worker-1",
            operation_id="lc_run--1",
            finished_at=datetime.now(UTC),
            duration_ms=10,
            usage=None,
        )
        await repository.finish(content="hello", **kwargs)
        self.db.commit()
        await repository.finish(content="hello", **kwargs)
        self.db.commit()
        with self.assertRaises(ValueError):
            await repository.finish(content="different", **kwargs)

    async def test_other_worker_cannot_write_audit(self):
        with self.assertRaises(RuntimeError):
            await ModelMessageAuditRepository(self.session).start(
                run_id="run-1",
                request_id="request-1",
                thread_id="thread-1",
                worker_id="worker-2",
                operation_id="lc_run--1",
                sequence=1,
                started_at=datetime.now(UTC),
            )

    async def test_reconcile_converts_audit_row_and_keeps_timing(self):
        message, _ = await self._start_model()
        self.db.commit()
        started_at = message.started_at
        repository = ModelMessageAuditRepository(self.session)
        await repository.finish(
            run_id="run-1",
            request_id="request-1",
            thread_id="thread-1",
            worker_id="worker-1",
            operation_id="lc_run--1",
            content="streamed",
            finished_at=datetime.now(UTC),
            duration_ms=120,
            usage=None,
        )
        self.db.commit()

        reconciled = await repository.reconcile_to_history(
            run_id="run-1",
            operation_id="lc_run--1",
            content="final",
            message_metadata={"langgraph_message_id": "lc_run--1"},
        )
        self.db.commit()
        self.assertIsNotNone(reconciled)
        self.assertEqual(reconciled.message_type, "text")
        self.assertEqual(reconciled.content, "final")
        self.assertEqual(reconciled.duration_ms, 120)
        self.assertEqual(reconciled.started_at, started_at)
        self.assertEqual(
            reconciled.msg_metadata["langgraph_message_id"], "lc_run--1"
        )
        self.assertEqual(len(self._messages()), 1)

    async def test_tool_audit_lifecycle_and_failure(self):
        repository = ToolMessageAuditRepository(self.session)
        await repository.start(
            run_id="run-1",
            request_id="request-1",
            thread_id="thread-1",
            worker_id="worker-1",
            tool_call_id="call-1",
            tool_name="calculator",
            tool_input={"a": 1},
            sequence=3,
            started_at=datetime.now(UTC),
        )
        self.db.commit()
        await repository.complete(
            run_id="run-1",
            request_id="request-1",
            thread_id="thread-1",
            worker_id="worker-1",
            tool_call_id="call-1",
            output={"content": "3"},
            content="3",
            finished_at=datetime.now(UTC),
            duration_ms=250,
            finished_sequence=4,
        )
        self.db.commit()
        row = self._messages(TOOL_AUDIT_MESSAGE_TYPE)[0]
        self.assertEqual(row.role, "tool")
        self.assertEqual(row.execution_status, "completed")
        self.assertEqual(row.content, "3")
        self.assertEqual(row.duration_ms, 250)
        self.assertEqual(row.msg_metadata["tool_name"], "calculator")

    async def test_history_excludes_audit_rows(self):
        await self._start_model()
        self.db.commit()
        history = await ConversationRepository(self.session).list_messages(
            conversation_id=1, limit=50
        )
        self.assertEqual([message.message_type for message in history], [])

        await ModelMessageAuditRepository(self.session).reconcile_to_history(
            run_id="run-1",
            operation_id="lc_run--1",
            content="final",
            message_metadata={"langgraph_message_id": "lc_run--1"},
        )
        self.db.commit()
        history = await ConversationRepository(self.session).list_messages(
            conversation_id=1, limit=50
        )
        self.assertEqual([message.content for message in history], ["final"])

    async def test_terminal_closes_running_audit_rows(self):
        await self._start_model()
        self.db.commit()
        run_repository = AgentRunRepository(self.session)
        closed = await run_repository.close_running_audit_messages(
            "run-1", execution_status="interrupted"
        )
        self.db.commit()
        self.assertEqual(closed, 1)
        row = self._messages(MODEL_AUDIT_MESSAGE_TYPE)[0]
        self.assertEqual(row.execution_status, "interrupted")
        self.assertIsNotNone(row.finished_at)

    async def test_terminal_close_preserves_observed_finish_time(self):
        repository = ToolMessageAuditRepository(self.session)
        await repository.start(
            run_id="run-1",
            request_id="request-1",
            thread_id="thread-1",
            worker_id="worker-1",
            tool_call_id="call-1",
            tool_name="calculator",
            tool_input={},
            sequence=3,
            started_at=datetime.now(UTC),
        )
        self.db.commit()
        observed = datetime(2026, 8, 3, 10, 0, tzinfo=UTC)
        await repository.observe_error(
            run_id="run-1",
            request_id="request-1",
            thread_id="thread-1",
            worker_id="worker-1",
            tool_call_id="call-1",
            error_message="boom",
            finished_at=observed,
            duration_ms=10,
            finished_sequence=5,
        )
        self.db.commit()

        await AgentRunRepository(self.session).close_running_audit_messages(
            "run-1", execution_status="interrupted"
        )
        self.db.commit()
        row = self._messages(TOOL_AUDIT_MESSAGE_TYPE)[0]
        self.assertEqual(row.execution_status, "interrupted")
        self.assertEqual(
            row.finished_at.replace(tzinfo=None), observed.replace(tzinfo=None)
        )

    async def test_next_sequence_ignores_audit_rows(self):
        await self._start_model(sequence=7)
        self.db.commit()
        repository = ConversationRepository(self.session)
        self.assertEqual(await repository.next_sequence(1), 1)
        message = await repository._create_message(
            conversation_id=1, role="user", content="hi"
        )
        self.db.commit()
        self.assertEqual(message.sequence, 1)
        self.assertEqual(message.execution_status, "completed")
        self.assertIsNotNone(message.started_at)


if __name__ == "__main__":
    unittest.main()
