"""Agent Run 终态写入测试。"""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

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
            "run-1",
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
                    finished_at=None,
                    error="old error",
                    error_type="OldError",
                )
                repository = AgentRunRepository(session)  # type: ignore[arg-type]
                repository._lock_update = AsyncMock(return_value=run)

                result, changed = await repository.set_agent_terminal(
                    "run-1",
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
                    finished_at=None,
                    error=None,
                    error_type=None,
                )
                repository = AgentRunRepository(session)  # type: ignore[arg-type]
                repository._lock_update = AsyncMock(return_value=run)

                result, changed = await repository.set_agent_terminal(
                    "run-1",
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
            await repository.set_agent_terminal("run-1", status="running")

        repository._lock_update.assert_not_awaited()
        self.assertEqual(0, session.flush_count)


if __name__ == "__main__":
    unittest.main()
