import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from server.service.arq_queue_servcie import RUN_REDIS_TTL_SECONDS
from server.worker import (
    AgentRunCancelRequested,
    AgentRunContext,
    StreamEventSmoother,
    _cancellable_stream,
    _finalize_run,
    map_stream_event,
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

                with self.assertRaises(AgentRunCancelRequested):
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
            conversation_id=None,
            content=None,
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
            conversation_id=None,
            content=None,
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
                conversation_id=1,
                content="done",
            )

        self.assertEqual(result, ("completed", False))
        write_end_event.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
