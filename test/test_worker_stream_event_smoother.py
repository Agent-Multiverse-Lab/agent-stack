import asyncio
import json
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from server.service.arq_queue_servcie import RUN_REDIS_TTL_SECONDS
from server.worker import (
    AgentRunContext,
    StreamEventSmoother,
    _cancellable_stream,
    _finalize_run,
    map_stream_event,
    process_agent_run,
    write_end_stream_event,
    write_stream_event,
)


class AgentRunContextTest(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_signal_interrupts_stream(self) -> None:
        cancel_signal = asyncio.Event()
        stream_started = asyncio.Event()

        async def wait_cancel_signal(run_id: str) -> bool:
            self.assertEqual("run-1", run_id)
            await cancel_signal.wait()
            return True

        async def stream():
            stream_started.set()
            await asyncio.Event().wait()
            yield ("messages", {})

        run_context = AgentRunContext("run-1")
        with patch(
            "server.worker.wait_agent_run_cancel_signal",
            new_callable=AsyncMock,
            side_effect=wait_cancel_signal,
        ) as wait_signal:
            run_context.start()
            try:
                next_chunk = asyncio.create_task(
                    anext(
                        _cancellable_stream(
                            stream(),
                            run_context=run_context,
                        )
                    )
                )
                await stream_started.wait()
                cancel_signal.set()

                with self.assertRaises(asyncio.CancelledError):
                    await next_chunk
            finally:
                await run_context.close()

        wait_signal.assert_awaited_once_with("run-1")

    async def test_close_reclaims_single_listener_task(self) -> None:
        listener_started = asyncio.Event()
        keep_listening = asyncio.Event()

        async def wait_cancel_signal(run_id: str) -> bool:
            self.assertEqual("run-1", run_id)
            listener_started.set()
            await keep_listening.wait()
            return True

        run_context = AgentRunContext("run-1")
        with patch(
            "server.worker.wait_agent_run_cancel_signal",
            new_callable=AsyncMock,
            side_effect=wait_cancel_signal,
        ) as wait_signal:
            run_context.start()
            run_context.start()
            await listener_started.wait()
            listener_task = run_context._cancel_listener_task

            await run_context.close()

        self.assertIsNotNone(listener_task)
        self.assertTrue(listener_task.cancelled())
        wait_signal.assert_awaited_once_with("run-1")


class StreamEventSmootherTest(unittest.IsolatedAsyncioTestCase):
    def test_maps_supported_stream_events(self) -> None:
        loading_chunk = {"status": "loading", "response": "hello"}
        self.assertEqual(
            map_stream_event(loading_chunk),
            ("messages", loading_chunk),
        )

        state = {"agent_todo": ["search"]}
        state_chunk = {"status": "agent_state", "response": state}
        self.assertEqual(
            map_stream_event(state_chunk),
            (
                "custom",
                {
                    "name": "agent_state",
                    "chunk": state_chunk,
                    "agent_state": state,
                },
            ),
        )

        with self.assertRaisesRegex(ValueError, "不支持的流事件状态"):
            map_stream_event({"status": "unknown"})

    async def test_append_releases_only_bucket_over_character_limit(
        self,
    ) -> None:
        smoother = StreamEventSmoother(run_id="run-1", character_limit=3)

        with (
            patch(
                "server.worker.StreamEventSmoother.calculate_character_count",
                side_effect=(2, 1, 1, 1),
            ),
            patch(
                "server.worker.write_stream_event",
                new_callable=AsyncMock,
            ) as write_event,
        ):
            await smoother.append(
                {"status": "loading", "sequence": 1},
                "thread-1",
            )
            await smoother.append(
                {"status": "loading", "sequence": 2},
                "thread-2",
            )
            await smoother.append(
                {"status": "loading", "sequence": 3},
                "thread-1",
            )
            write_event.assert_not_awaited()

            await smoother.append(
                {"status": "loading", "sequence": 4},
                "thread-1",
            )

        write_event.assert_awaited_once_with(
            "run-1",
            "messages",
            {
                "items": [
                    {"status": "loading", "sequence": 1},
                    {"status": "loading", "sequence": 3},
                    {"status": "loading", "sequence": 4},
                ]
            },
            "thread-1",
        )
        self.assertEqual(smoother.chunk_buckets["thread-1"].chunks, [])
        self.assertEqual(smoother.chunk_buckets["thread-1"].char_counts, 0)
        self.assertEqual(
            smoother.chunk_buckets["thread-2"].chunks,
            [{"status": "loading", "sequence": 2}],
        )
        self.assertEqual(smoother.chunk_buckets["thread-2"].char_counts, 1)


class WorkerStreamWriterTest(unittest.IsolatedAsyncioTestCase):
    async def test_write_stream_event_forwards_payload(self) -> None:
        payload = {"status": "running"}
        with patch(
            "server.worker.write_agent_run_stream_event",
            new_callable=AsyncMock,
            return_value="1-0",
        ) as write_event:
            event_id = await write_stream_event(
                "run-1",
                "status",
                payload,
                "thread-1",
            )

        self.assertEqual("1-0", event_id)
        write_event.assert_awaited_once_with(
            "run-1",
            "status",
            payload,
            "thread-1",
            ttl_seconds=RUN_REDIS_TTL_SECONDS,
        )
        self.assertIs(payload, write_event.await_args.args[2])

    async def test_write_end_stream_event_writes_same_payload(self) -> None:
        payload = {"status": "completed", "result": "done"}
        with patch(
            "server.worker.write_stream_event",
            new_callable=AsyncMock,
            return_value="2-0",
        ) as write_event:
            event_id = await write_end_stream_event(
                "run-1",
                payload,
                "thread-1",
            )

        self.assertEqual("2-0", event_id)
        write_event.assert_awaited_once_with(
            "run-1",
            "end",
            payload,
            "thread-1",
        )
        self.assertIs(payload, write_event.await_args.args[2])


class AgentRunFinalizationTest(unittest.IsolatedAsyncioTestCase):
    async def test_interrupted_run_persists_before_interaction_and_end(self) -> None:
        # FIXEME: finalizer 统一保证 interrupt 落库和事件发布顺序。
        events = []
        payload = {
            "kind": "ask_user",
            "question": "请选择数据库",
            "options": ["PostgreSQL", "MySQL"],
        }

        async def set_terminal(run_id, **kwargs):
            events.append(("persist", run_id, kwargs))
            return "interrupted", True

        async def write_event(run_id, event_type, event_payload, thread_id):
            events.append((event_type, run_id, event_payload, thread_id))

        async def write_end(run_id, event_payload, thread_id):
            events.append(("end", run_id, event_payload, thread_id))

        with (
            patch(
                "server.worker.set_run_terminal",
                side_effect=set_terminal,
            ),
            patch("server.worker.write_stream_event", side_effect=write_event),
            patch("server.worker.write_end_stream_event", side_effect=write_end),
        ):
            result = await _finalize_run(
                "parent-run",
                status="interrupted",
                thread_id="thread-1",
                payload=payload,
            )

        self.assertEqual(("interrupted", True), result)
        self.assertEqual(
            ["persist", "interaction_required", "end"],
            [event[0] for event in events],
        )
        self.assertEqual("interrupted", events[0][2]["status"])
        self.assertEqual(
            payload,
            json.loads(events[0][2]["error"]),
        )
        self.assertEqual("ask_user", events[0][2]["error_type"])
        self.assertEqual("parent-run", events[1][2]["parent_run_id"])

    async def test_failed_run_uses_unified_terminal_path(self) -> None:
        with (
            patch(
                "server.worker.set_run_terminal",
                new_callable=AsyncMock,
                return_value=("failed", True),
            ) as set_terminal,
            patch(
                "server.worker.write_end_stream_event",
                new_callable=AsyncMock,
            ) as write_end_event,
            patch(
                "server.worker.clear_agent_run_cancel_signal",
                new_callable=AsyncMock,
            ) as clear_cancel,
        ):
            result = await _finalize_run(
                "run-1",
                status="failed",
                thread_id="thread-1",
                error="boom",
                error_type="RuntimeError",
            )

        self.assertEqual(result, ("failed", True))
        set_terminal.assert_awaited_once_with(
            "run-1",
            status="failed",
            error="boom",
            error_type="RuntimeError",
        )
        write_end_event.assert_awaited_once_with(
            "run-1",
            {
                "status": "failed",
                "error": "boom",
            },
            "thread-1",
        )
        clear_cancel.assert_not_awaited()

    async def test_cancelled_run_writes_end_and_clears_signal(self) -> None:
        with (
            patch(
                "server.worker.set_run_terminal",
                new_callable=AsyncMock,
                return_value=("cancelled", True),
            ) as set_terminal,
            patch(
                "server.worker.write_end_stream_event",
                new_callable=AsyncMock,
            ) as write_end_event,
            patch(
                "server.worker.clear_agent_run_cancel_signal",
                new_callable=AsyncMock,
            ) as clear_cancel,
        ):
            result = await _finalize_run(
                "run-1",
                status="cancelled",
                thread_id="thread-1",
            )

        self.assertEqual(result, ("cancelled", True))
        set_terminal.assert_awaited_once_with(
            "run-1",
            status="cancelled",
            error=None,
            error_type=None,
        )
        write_end_event.assert_awaited_once_with(
            "run-1",
            {"status": "cancelled"},
            "thread-1",
        )
        clear_cancel.assert_awaited_once_with("run-1")

    async def test_unchanged_terminal_run_does_not_write_end(self) -> None:
        with (
            patch(
                "server.worker.set_run_terminal",
                new_callable=AsyncMock,
                return_value=("completed", False),
            ),
            patch(
                "server.worker.write_end_stream_event",
                new_callable=AsyncMock,
            ) as write_end_event,
        ):
            result = await _finalize_run(
                "run-1",
                status="completed",
                thread_id="thread-1",
            )

        self.assertEqual(result, ("completed", False))
        write_end_event.assert_not_awaited()


# FIXEME: Agent Stream 前的退出只写 Repository 终态，不通过 finalizer 发布 end。
class AgentRunPreStreamFailureTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _agent_run(**overrides):
        values = {
            "id": "run-1",
            "agent_status": "queued",
            "uid": "user-1",
            "agent_id": "leader-agent",
            "request_id": "request-1",
            "thread_id": "thread-1",
            "run_type": "resume",
            "run_metadata": {"resume": {"answer": "PostgreSQL"}},
            "trigger_message_id": None,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    async def test_missing_input_sets_failed_without_finalizer(self) -> None:
        agent_run = self._agent_run(
            run_type="normal",
            run_metadata={},
            trigger_message_id=101,
        )

        with (
            patch(
                "server.worker._get_agent_run",
                new_callable=AsyncMock,
                return_value=agent_run,
            ),
            patch(
                "server.worker._get_agent_input_msg",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "server.worker.set_run_terminal",
                new_callable=AsyncMock,
            ) as set_terminal,
            patch(
                "server.worker._finalize_run",
                new_callable=AsyncMock,
            ) as finalizer,
            patch(
                "server.worker.write_end_stream_event",
                new_callable=AsyncMock,
            ) as write_end,
        ):
            result = await process_agent_run({}, "run-1")

        self.assertIsNone(result)
        set_terminal.assert_awaited_once_with(
            "run-1",
            status="failed",
            error="Input message not found: 101",
            error_type="LookupError",
        )
        finalizer.assert_not_awaited()
        write_end.assert_not_awaited()

    async def test_missing_user_sets_failed_without_finalizer(self) -> None:
        with (
            patch(
                "server.worker._get_agent_run",
                new_callable=AsyncMock,
                return_value=self._agent_run(),
            ),
            patch(
                "server.worker._get_user",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "server.worker.set_run_terminal",
                new_callable=AsyncMock,
            ) as set_terminal,
            patch(
                "server.worker._finalize_run",
                new_callable=AsyncMock,
            ) as finalizer,
            patch(
                "server.worker.write_end_stream_event",
                new_callable=AsyncMock,
            ) as write_end,
        ):
            result = await process_agent_run({}, "run-1")

        self.assertIsNone(result)
        set_terminal.assert_awaited_once_with(
            "run-1",
            status="failed",
            error="User not found: user-1",
            error_type="LookupError",
        )
        finalizer.assert_not_awaited()
        write_end.assert_not_awaited()

    async def test_pre_stream_cancel_sets_terminal_without_end(self) -> None:
        with (
            patch(
                "server.worker._get_agent_run",
                new_callable=AsyncMock,
                return_value=self._agent_run(),
            ),
            patch(
                "server.worker._get_user",
                new_callable=AsyncMock,
                return_value=SimpleNamespace(uid="user-1"),
            ),
            patch(
                "server.worker.set_run_running",
                new_callable=AsyncMock,
                return_value=SimpleNamespace(agent_status="cancel_requested"),
            ),
            patch(
                "server.worker.set_run_terminal",
                new_callable=AsyncMock,
            ) as set_terminal,
            patch(
                "server.worker.clear_agent_run_cancel_signal",
                new_callable=AsyncMock,
            ) as clear_cancel,
            patch(
                "server.worker._finalize_run",
                new_callable=AsyncMock,
            ) as finalizer,
            patch(
                "server.worker.write_end_stream_event",
                new_callable=AsyncMock,
            ) as write_end,
        ):
            result = await process_agent_run({}, "run-1")

        self.assertIsNone(result)
        set_terminal.assert_awaited_once_with("run-1", status="cancelled")
        clear_cancel.assert_awaited_once_with("run-1")
        finalizer.assert_not_awaited()
        write_end.assert_not_awaited()


# FIXEME: 终态 chunk 必须在 process_agent_run 中按 status 驱动自然收口。
class AgentRunProcessTest(unittest.IsolatedAsyncioTestCase):
    async def _run_process(
        self,
        chunks: list[dict],
        *,
        final_status: str,
        changed: bool = True,
        has_cancel_signal: bool = False,
    ):
        events: list[tuple] = []
        agent_run = SimpleNamespace(
            id="run-1",
            agent_status="queued",
            uid="user-1",
            agent_id="leader-agent",
            request_id="request-1",
            thread_id="thread-1",
            run_type="resume",
            run_metadata={"resume": {"answer": "PostgreSQL"}},
            trigger_message_id=None,
        )
        user = SimpleNamespace(uid="user-1")
        running_run = SimpleNamespace(agent_status="running")

        async def stream_response(**_kwargs):
            for chunk in chunks:
                chunk.setdefault("thread_id", "thread-1")
                yield (json.dumps(chunk) + "\n").encode("utf-8")

        async def passthrough_stream(stream, **_kwargs):
            async for chunk in stream:
                yield chunk

        async def set_terminal(
            run_id,
            *,
            status,
            error=None,
            error_type=None,
        ):
            events.append(
                (
                    "finalize",
                    status,
                    {"error": error, "error_type": error_type},
                )
            )
            return final_status, changed

        async def write_event(run_id, event_type, payload, thread_id):
            events.append((event_type, payload, thread_id))
            return "1-0"

        async def write_end(run_id, payload, thread_id):
            events.append(("end", payload, thread_id))
            return "2-0"

        @asynccontextmanager
        async def session_context():
            yield object()

        with (
            patch(
                "server.worker._get_agent_run",
                new_callable=AsyncMock,
                return_value=agent_run,
            ),
            patch(
                "server.worker._get_user",
                new_callable=AsyncMock,
                return_value=user,
            ),
            patch(
                "server.worker.set_run_running",
                new_callable=AsyncMock,
                return_value=running_run,
            ),
            patch(
                "server.worker.resume_agent_response",
                side_effect=lambda **kwargs: stream_response(**kwargs),
            ),
            patch("server.worker._cancellable_stream", new=passthrough_stream),
            patch(
                "server.worker.postgres_manager.get_async_session_context",
                return_value=session_context(),
            ),
            patch("server.worker.set_run_terminal", side_effect=set_terminal),
            patch("server.worker._finalize_run", wraps=_finalize_run) as finalizer,
            patch("server.worker.write_stream_event", side_effect=write_event),
            patch("server.worker.write_end_stream_event", side_effect=write_end),
            patch(
                "server.worker.clear_agent_run_cancel_signal",
                new_callable=AsyncMock,
            ),
            patch("server.worker.AgentRunContext.start"),
            patch(
                "server.worker.AgentRunContext.has_cancel_signal",
                new_callable=AsyncMock,
                return_value=has_cancel_signal,
            ),
            patch(
                "server.worker.AgentRunContext.close",
                new_callable=AsyncMock,
            ),
        ):
            result = await process_agent_run({}, "run-1")

        return result, finalizer, events

    async def test_interrupted_status_uses_finalizer(self) -> None:
        interrupt = {
            "kind": "ask_user",
            "question": "请选择数据库",
            "options": ["PostgreSQL", "MySQL"],
        }

        result, finalizer, events = await self._run_process(
            [{"status": "interrupted", "interrupt": interrupt}],
            final_status="interrupted",
        )

        self.assertIsNone(result)
        self.assertEqual(
            ["status", "finalize", "interaction_required", "end", "end"],
            [event[0] for event in events],
        )
        self.assertEqual(
            interrupt,
            finalizer.await_args.kwargs["payload"],
        )
        self.assertEqual("interrupted", events[-1][1]["status"])
        self.assertEqual("interrupted", events[-1][1]["chunk"]["status"])
        self.assertEqual(interrupt, events[-1][1]["chunk"]["interrupt"])

    async def test_unchanged_interrupted_status_does_not_publish(self) -> None:
        result, finalizer, events = await self._run_process(
            [
                {
                    "status": "interrupted",
                    "interrupt": {
                        "kind": "ask_user",
                        "question": "请选择数据库",
                        "options": ["PostgreSQL"],
                    },
                }
            ],
            final_status="interrupted",
            changed=False,
        )

        self.assertIsNone(result)
        self.assertEqual(
            ["status", "finalize"],
            [event[0] for event in events],
        )
        finalizer.assert_awaited_once()

    async def test_error_status_maps_to_failed(self) -> None:
        result, finalizer, events = await self._run_process(
            [
                {
                    "status": "error",
                    "error": "model failed",
                    "error_type": "RuntimeError",
                }
            ],
            final_status="failed",
        )

        self.assertIsNone(result)
        self.assertEqual("failed", finalizer.await_args.kwargs["status"])
        self.assertEqual("model failed", finalizer.await_args.kwargs["error"])
        self.assertEqual(
            "RuntimeError",
            finalizer.await_args.kwargs["error_type"],
        )
        self.assertEqual(
            ["status", "finalize", "end", "end"],
            [event[0] for event in events],
        )
        self.assertEqual("failed", events[-1][1]["status"])
        self.assertEqual("error", events[-1][1]["chunk"]["status"])
        self.assertEqual("model failed", events[-1][1]["chunk"]["error"])

    async def test_unchanged_error_uses_actual_terminal_status_for_flag(
        self,
    ) -> None:
        result, finalizer, events = await self._run_process(
            [
                {
                    "status": "error",
                    "error": "late error",
                    "error_type": "RuntimeError",
                }
            ],
            final_status="completed",
            changed=False,
        )

        self.assertIsNone(result)
        self.assertEqual(
            ["status", "finalize"],
            [event[0] for event in events],
        )
        finalizer.assert_awaited_once()

    async def test_finished_status_maps_to_completed(self) -> None:
        result, finalizer, events = await self._run_process(
            [{"status": "finished", "request_id": "request-1"}],
            final_status="completed",
        )

        self.assertIsNone(result)
        self.assertEqual("completed", finalizer.await_args.kwargs["status"])
        self.assertEqual(
            "finished",
            finalizer.await_args.kwargs["payload"]["status"],
        )
        self.assertEqual(
            ["status", "finalize", "end", "end"],
            [event[0] for event in events],
        )
        self.assertEqual("completed", events[-1][1]["status"])
        self.assertEqual("finished", events[-1][1]["chunk"]["status"])

    async def test_unchanged_finished_status_does_not_publish_end(self) -> None:
        # FIXEME: case 只在本次数据库状态发生变化时发布终止事件。
        result, _, events = await self._run_process(
            [{"status": "finished", "request_id": "request-1"}],
            final_status="completed",
            changed=False,
        )

        self.assertIsNone(result)
        self.assertEqual(
            ["status", "finalize"],
            [event[0] for event in events],
        )

    async def test_chunks_after_terminal_flag_still_follow_status(self) -> None:
        # terminal_flag 只在循环结束后读取，不屏蔽后续 chunk。
        result, _, events = await self._run_process(
            [
                {"status": "finished", "request_id": "request-1"},
                {"status": "agent_state", "response": {"agent_todo": []}},
            ],
            final_status="completed",
        )

        self.assertIsNone(result)
        self.assertEqual(
            ["status", "finalize", "end", "end", "custom"],
            [event[0] for event in events],
        )

    async def test_stream_without_terminal_uses_context_cancellation(self) -> None:
        # 无 terminal_flag 时先由 Run Context 判定取消。
        result, finalizer, _ = await self._run_process(
            [],
            final_status="cancelled",
            has_cancel_signal=True,
        )

        self.assertEqual(("cancelled", True), result)
        self.assertEqual("cancelled", finalizer.await_args.kwargs["status"])

    async def test_stream_without_terminal_status_maps_to_failed(self) -> None:
        result, finalizer, _ = await self._run_process(
            [],
            final_status="failed",
        )

        self.assertEqual(("failed", True), result)
        self.assertEqual("failed", finalizer.await_args.kwargs["status"])
        self.assertEqual(
            "Agent stream ended without terminal status",
            finalizer.await_args.kwargs["error"],
        )


if __name__ == "__main__":
    unittest.main()
