import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, call, patch

from server.service.arq_queue_servcie import RUN_REDIS_TTL_SECONDS
from server.worker import StreamEventSmoother, _finalize_run, map_stream_event


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
                "server.worker.calculate_character_count",
                side_effect=(2, 1, 1, 1),
            ),
            patch(
                "server.worker.write_agent_run_stream_event",
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
            {
                "type": "messages",
                "thread_id": "thread-1",
                "payload": {
                    "items": [
                        {"status": "loading", "sequence": 1},
                        {"status": "loading", "sequence": 3},
                        {"status": "loading", "sequence": 4},
                    ]
                },
            },
            ttl_seconds=RUN_REDIS_TTL_SECONDS,
        )
        self.assertEqual(smoother.chunk_buckets["thread-1"].chunks, [])
        self.assertEqual(smoother.chunk_buckets["thread-1"].char_counts, 0)
        self.assertEqual(
            smoother.chunk_buckets["thread-2"].chunks,
            [{"status": "loading", "sequence": 2}],
        )
        self.assertEqual(smoother.chunk_buckets["thread-2"].char_counts, 1)


class AgentRunFinalizationTest(unittest.IsolatedAsyncioTestCase):
    async def test_failed_run_uses_unified_terminal_path(self) -> None:
        with (
            patch(
                "server.worker.set_run_terminal",
                new_callable=AsyncMock,
                return_value=SimpleNamespace(agent_status="failed"),
            ) as set_terminal,
            patch(
                "server.worker.publish_agent_run_event",
                new_callable=AsyncMock,
            ) as publish_event,
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

        self.assertEqual(result, {"run_id": "run-1", "status": "failed"})
        set_terminal.assert_awaited_once_with(
            "run-1",
            status="failed",
            error="boom",
            error_type="RuntimeError",
        )
        publish_event.assert_awaited_once_with(
            "run-1",
            {
                "type": "end",
                "status": "failed",
                "thread_id": "thread-1",
                "error": "boom",
            },
        )
        clear_cancel.assert_not_awaited()

    async def test_cancel_requested_finishes_as_cancelled(self) -> None:
        with (
            patch(
                "server.worker.set_run_terminal",
                new_callable=AsyncMock,
                side_effect=(
                    SimpleNamespace(agent_status="cancel_requested"),
                    SimpleNamespace(agent_status="cancelled"),
                ),
            ) as set_terminal,
            patch(
                "server.worker.publish_agent_run_event",
                new_callable=AsyncMock,
            ) as publish_event,
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

        self.assertEqual(result, {"run_id": "run-1", "status": "cancelled"})
        self.assertEqual(
            set_terminal.await_args_list,
            [
                call(
                    "run-1",
                    status="failed",
                    error="boom",
                    error_type="RuntimeError",
                ),
                call(
                    "run-1",
                    status="cancelled",
                    error=None,
                    error_type=None,
                ),
            ],
        )
        publish_event.assert_awaited_once_with(
            "run-1",
            {
                "type": "end",
                "status": "cancelled",
                "thread_id": "thread-1",
            },
        )
        clear_cancel.assert_awaited_once_with("run-1")


if __name__ == "__main__":
    unittest.main()
