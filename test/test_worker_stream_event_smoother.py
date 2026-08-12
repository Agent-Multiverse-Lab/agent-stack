import unittest
from unittest.mock import AsyncMock, patch

from server.worker import StreamEventSmoother, map_stream_event


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
                "server.worker.write_agent_run_event",
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
            run_id="run-1",
            payload={
                "items": [
                    {"status": "loading", "sequence": 1},
                    {"status": "loading", "sequence": 3},
                    {"status": "loading", "sequence": 4},
                ]
            },
            event_type="messages",
            thread_id="thread-1",
        )
        self.assertEqual(smoother.chunk_buckets["thread-1"].chunks, [])
        self.assertEqual(smoother.chunk_buckets["thread-1"].char_counts, 0)
        self.assertEqual(
            smoother.chunk_buckets["thread-2"].chunks,
            [{"status": "loading", "sequence": 2}],
        )
        self.assertEqual(smoother.chunk_buckets["thread-2"].char_counts, 1)


if __name__ == "__main__":
    unittest.main()
