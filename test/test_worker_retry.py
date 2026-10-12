"""隔离外部服务，验证 Worker 重试与 SQL 终态边界。"""

import ast
import asyncio
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from arq.connections import RedisSettings
from arq.worker import RetryJob
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from sqlalchemy.exc import DisconnectionError, OperationalError


class WorkerRetryTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.run = SimpleNamespace(
            id="run-1", agent_status="queued", uid="user-1", agent_id="leader",
            thread_id="thread-1", request_id="request-1", run_type="chat",
            trigger_message_id=1, parent_run_id=None, run_metadata={},
        )
        self.controller = SimpleNamespace(
            start=Mock(), close=AsyncMock(), is_cancelled=AsyncMock(return_value=False),
        )
        self.chunks = [{"status": "finished"}]
        self.stream_error = None

        @asynccontextmanager
        async def session():
            yield None

        async def stream(**kwargs):
            if self.stream_error is not None:
                raise self.stream_error
            for chunk in self.chunks:
                yield chunk

        async def cancellable_stream(iterator, **kwargs):
            async for chunk in iterator:
                yield chunk

        async def finalize(run_id, *, status, **kwargs):
            self.run.agent_status = status
            return status, True

        self.namespace = {
            "RetryJob": RetryJob, "RedisSettings": RedisSettings,
            "asyncio": asyncio, "logger": Mock(),
            "config": SimpleNamespace(arq_queue_name="test-runs", arq_max_jobs=1, redis_url="redis://localhost:6379/0"),
            "startup": AsyncMock(), "shutdown": AsyncMock(),
            "AGENT_RUN_TERMINAL_STATUSES": frozenset({"completed", "failed", "cancelled", "interrupted"}),
            "_get_agent_run": AsyncMock(return_value=self.run),
            "_get_agent_input_msg": AsyncMock(return_value=SimpleNamespace(content="hello", message_type="human", image_content=None, msg_metadata={})),
            "_get_user": AsyncMock(return_value=SimpleNamespace(uid="user-1")),
            "build_agent_input_msg": Mock(return_value="input"),
            "set_run_running": AsyncMock(return_value=self.run),
            "set_run_terminal": AsyncMock(return_value=("failed", True)),
            "clear_agent_run_cancel_signal": AsyncMock(),
            "write_stream_event": AsyncMock(), "write_end_stream_event": AsyncMock(),
            "AgentRunController": Mock(return_value=self.controller),
            "StreamEventSmoother": Mock(return_value=SimpleNamespace(release=AsyncMock(), append=AsyncMock())),
            "postgres_manager": SimpleNamespace(get_async_session_context=session),
            "stream_agent_response": stream, "resume_agent_response": stream,
            "_cancellable_stream": cancellable_stream,
            "_normalize_steam_agent_chunk": lambda chunk: [chunk],
            "reslove_thread_id": lambda chunk, thread_id: thread_id,
            "map_stream_event": Mock(return_value=("status", {})),
            "_finalize_run": AsyncMock(side_effect=finalize),
        }
        # 加载生产函数的原始 AST，避免导入应用时加载 .env 或连接基础设施。
        path = Path(__file__).resolve().parents[1] / "server" / "worker.py"
        source = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        nodes = [
            node for node in source.body
            if isinstance(node, (ast.AsyncFunctionDef, ast.ClassDef))
            and node.name in {
                "RetryableWorkerError", "process_agent_run", "_process_agent_run", "WorkerSettings",
            }
        ]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), self.namespace)
        self.process = self.namespace["process_agent_run"]
        self.retryable_error = self.namespace["RetryableWorkerError"]

    async def test_preparation_retryable_errors_raise_retry_job_without_terminal(self):
        errors = [
            RetryJob("retryable"),
            self.retryable_error("retryable"),
        ]
        for job_try in (1, 2):
            for error in errors:
                with self.subTest(job_try=job_try, error=type(error).__name__):
                    self.namespace["_get_agent_run"].side_effect = error
                    with self.assertRaises(RetryJob) as raised:
                        await self.process({"job_try": job_try}, "run-1")
                    self.assertIs(raised.exception, error)
        self.namespace["set_run_terminal"].assert_not_awaited()
        self.namespace["write_stream_event"].assert_not_awaited()
        self.namespace["_finalize_run"].assert_not_awaited()

    async def test_ordinary_preparation_errors_fail_without_retry(self):
        class ApplicationError(Exception):
            pass

        errors = [
            Exception("error"), ApplicationError("error"),
            ConnectionError("offline"), TimeoutError("timeout"),
            RedisConnectionError("offline"), RedisTimeoutError("timeout"),
            DisconnectionError("offline"), OperationalError(None, None, ConnectionError("offline")),
        ]
        for job_try in (1, 3):
            for error in errors:
                with self.subTest(job_try=job_try, error=type(error).__name__):
                    self.namespace["set_run_terminal"].reset_mock()
                    self.namespace["_get_user"].side_effect = error
                    with self.assertRaises(type(error)) as raised:
                        await self.process({"job_try": job_try}, "run-1")
                    self.assertIs(raised.exception, error)
                    self.assertNotIsInstance(raised.exception, RetryJob)
                    self.namespace["set_run_terminal"].assert_awaited_once_with(
                        "run-1", status="failed", error=str(error), error_type=type(error).__name__,
                    )
        self.namespace["_finalize_run"].assert_not_awaited()

    async def test_retry_reloads_run_and_executes_agent_once_after_recovery(self):
        self.namespace["_get_agent_run"].side_effect = [self.retryable_error("retryable"), self.run]
        with self.assertRaises(RetryJob):
            await self.process({"job_try": 1}, "run-1")
        await self.process({"job_try": 2}, "run-1")
        self.assertEqual(self.namespace["_get_agent_run"].await_count, 2)
        self.namespace["set_run_terminal"].assert_not_awaited()
        self.namespace["AgentRunController"].assert_called_once_with("run-1")
        self.namespace["_finalize_run"].assert_awaited_once()
        self.assertEqual(self.run.agent_status, "completed")

    async def test_initial_stream_publication_failure_is_not_retried_and_closes_listener(self):
        self.namespace["write_stream_event"].side_effect = RedisConnectionError("offline")
        with self.assertRaises(RedisConnectionError):
            await self.process({"job_try": 1}, "run-1")
        self.controller.close.assert_awaited_once()
        self.namespace["_finalize_run"].assert_not_awaited()
        self.namespace["set_run_terminal"].assert_awaited_once_with(
            "run-1", status="failed", error="offline", error_type="ConnectionError",
        )

    async def test_session_connection_failure_is_not_retried_before_stream_starts(self):
        @asynccontextmanager
        async def failed_session():
            raise ConnectionError("offline")
            yield

        self.namespace["postgres_manager"].get_async_session_context = failed_session
        with self.assertRaises(ConnectionError):
            await self.process({"job_try": 1}, "run-1")
        self.namespace["_finalize_run"].assert_not_awaited()
        self.controller.close.assert_awaited_once()
        self.namespace["set_run_terminal"].assert_awaited_once_with(
            "run-1", status="failed", error="offline", error_type="ConnectionError",
        )

    async def test_stream_connection_failure_is_finalized_without_replaying_agent(self):
        self.stream_error = ConnectionError("offline")
        with self.assertRaises(ConnectionError):
            await self.process({"job_try": 1}, "run-1")
        self.assertEqual(self.run.agent_status, "failed")
        self.namespace["_finalize_run"].assert_awaited_once()
        self.controller.close.assert_awaited_once()

    async def test_explicit_retry_job_exhaustion_stops_arq_retry(self):
        for error in (RetryJob("retryable"), self.retryable_error("retryable")):
            with self.subTest(error=type(error).__name__):
                self.namespace["set_run_terminal"].reset_mock()
                self.namespace["_get_user"].side_effect = error
                with self.assertRaises(RuntimeError) as raised:
                    await self.process({"job_try": 3}, "run-1")
                self.assertNotIsInstance(raised.exception, RetryJob)
                self.assertIs(raised.exception.__cause__, error)
                self.namespace["set_run_terminal"].assert_awaited_once_with(
                    "run-1", status="failed", error="retryable", error_type=type(error).__name__,
                )

    async def test_retry_job_after_stream_start_is_finalized_without_retry(self):
        self.stream_error = RetryJob("retryable")
        with self.assertRaises(RuntimeError) as raised:
            await self.process({"job_try": 1}, "run-1")
        self.assertNotIsInstance(raised.exception, RetryJob)
        self.assertIs(raised.exception.__cause__, self.stream_error)
        self.assertEqual(self.run.agent_status, "failed")
        self.namespace["_finalize_run"].assert_awaited_once()
        self.controller.close.assert_awaited_once()

    async def test_cancellation_on_retry_keeps_existing_pre_stream_flow(self):
        self.run.agent_status = "cancel_requested"
        await self.process({"job_try": 2}, "run-1")
        self.namespace["set_run_terminal"].assert_awaited_once_with("run-1", status="cancelled")
        self.namespace["clear_agent_run_cancel_signal"].assert_awaited_once_with("run-1")
        self.namespace["AgentRunController"].assert_not_called()

    async def test_terminal_run_is_not_restarted_on_retry(self):
        for status in ("completed", "failed", "cancelled", "interrupted"):
            with self.subTest(status=status):
                self.run.agent_status = status
                result = await self.process({"job_try": 2}, "run-1")
                self.assertEqual(result, {"run_id": "run-1", "status": status})
        self.namespace["set_run_running"].assert_not_awaited()

    async def test_missing_input_is_a_permanent_failure(self):
        self.namespace["_get_agent_input_msg"].return_value = None
        await self.process({"job_try": 1}, "run-1")
        self.namespace["set_run_terminal"].assert_awaited_once_with(
            "run-1", status="failed", error="Input message not found: 1", error_type="LookupError",
        )

    async def test_business_error_chunk_is_not_retried(self):
        self.chunks = [{"status": "error", "error": "invalid", "error_type": "ValueError"}]
        await self.process({"job_try": 1}, "run-1")
        self.assertEqual(self.run.agent_status, "failed")
        self.namespace["_finalize_run"].assert_awaited_once()

    async def test_user_cancellation_during_stream_is_not_retried(self):
        self.stream_error = asyncio.CancelledError()
        result = await self.process({"job_try": 1}, "run-1")
        self.assertEqual(result, ("cancelled", True))
        self.controller.close.assert_awaited_once()

    async def test_value_error_during_preparation_is_not_retried(self):
        self.namespace["_get_user"].side_effect = ValueError("invalid")
        with self.assertRaises(ValueError):
            await self.process({"job_try": 1}, "run-1")
        self.namespace["set_run_terminal"].assert_awaited_once_with(
            "run-1", status="failed", error="invalid", error_type="ValueError",
        )


if __name__ == "__main__":
    unittest.main()
