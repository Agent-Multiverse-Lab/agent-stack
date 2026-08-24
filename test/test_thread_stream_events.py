import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from langchain.messages import HumanMessage

from server.service import thread_service


class FakeAgent:
    def __init__(self, events=(), error: Exception | None = None) -> None:
        self.events = events
        self.error = error

    async def stream_messages_with_event(self, *_args, **_kwargs):
        if self.error is not None:
            raise self.error
        for event in self.events:
            yield event


class ThreadStreamEventTest(unittest.IsolatedAsyncioTestCase):
    async def collect_events(self, agent: FakeAgent) -> list[dict]:
        agent_item = SimpleNamespace(slug="test-agent")
        input_message = SimpleNamespace(
            content="hello",
            image_content=None,
            langchain_msg=HumanMessage(content="hello"),
        )
        current_user = SimpleNamespace(uid="user-1")
        save_messages = AsyncMock()
        self.save_messages = save_messages

        with (
            patch(
                "server.service.thread_service._build_agent_runtime",
                new_callable=AsyncMock,
                return_value=(agent_item, agent),
            ),
            patch(
                "server.service.thread_service._build_agent_runtime_context",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "server.service.thread_service.ConversationRepository",
                return_value=object(),
            ),
            patch(
                "server.service.thread_service._check_conv_status",
                new_callable=AsyncMock,
            ),
            patch(
                "server.service.thread_service.save_message_from_langgraph_state",
                new=save_messages,
            ),
        ):
            return [
                json.loads(chunk)
                async for chunk in thread_service.stream_agent_response(
                    agent_slug="test-agent",
                    thread_id="thread-1",
                    runtime_metadata={
                        "run_id": "run-1",
                        "request_id": "request-1",
                        "thread_id": "thread-1",
                    },
                    thread_input_message=input_message,
                    current_user=current_user,
                    db=object(),
                )
            ]

    async def test_v3_delta_populates_loading_response(self) -> None:
        metadata = {"run_id": "model-run-1"}
        events = await self.collect_events(
            FakeAgent(
                events=(
                    (
                        "messages",
                        (
                            {
                                "event": "message-start",
                                "role": "ai",
                                "id": "message-1",
                            },
                            metadata,
                        ),
                    ),
                    (
                        "messages",
                        (
                            {
                                "event": "content-block-delta",
                                "index": 0,
                                "delta": {"type": "text-delta", "text": "OK"},
                            },
                            metadata,
                        ),
                    ),
                )
            )
        )

        loading_event = events[0]
        self.assertEqual("loading", loading_event["status"])
        self.assertEqual("OK", loading_event["response"])
        self.assertEqual(
            "OK",
            loading_event["stream_event"][0]["content_delta"],
        )
        self.assertEqual("finished", events[1]["status"])
        self.save_messages.assert_awaited_once()

    async def test_invalid_values_payload_propagates(self) -> None:
        with self.assertRaises(AttributeError):
            await self.collect_events(FakeAgent(events=(("values", None),)))

    async def test_agent_stream_error_propagates(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "model failed"):
            await self.collect_events(
                FakeAgent(error=RuntimeError("model failed"))
            )


if __name__ == "__main__":
    unittest.main()
