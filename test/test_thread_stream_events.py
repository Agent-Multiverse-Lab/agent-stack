import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from langchain.messages import HumanMessage

from server.service import thread_service


class FakeContext:
    def update_context(self, values: dict) -> None:
        for key, value in values.items():
            setattr(self, key, value)


class FakeAgent:
    agent_context = FakeContext

    def __init__(self, events=(), error: Exception | None = None) -> None:
        self.events = events
        self.error = error

    async def stream_messages_with_event(self, *_args, **_kwargs):
        if self.error is not None:
            raise self.error
        for event in self.events:
            yield event

    async def stream_message_by_resume(self, resume_input, **_kwargs):
        self.resume_input = resume_input
        if self.error is not None:
            raise self.error
        for event in self.events:
            yield event


class ThreadStreamEventTest(unittest.IsolatedAsyncioTestCase):
    async def test_runtime_context_includes_selected_model(self):
        context = await thread_service._build_agent_runtime_context(
            uid="user-1",
            run_id="run-1",
            thread_id="thread-1",
            request_id="request-1",
            model="dashscope/qwen3.8-max",
        )

        self.assertEqual("dashscope/qwen3.8-max", context["model"])

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
            # FIXEME: 流事件单测不重复验证 checkpoint interrupt fixture。
            patch(
                "server.service.thread_service.check_agent_interrupt_handler",
                new_callable=AsyncMock,
                return_value=None,
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
        self.assertEqual("run-1", self.save_messages.await_args.kwargs["run_id"])

    async def test_invalid_values_payload_yields_error_chunk(self) -> None:
        # FIXEME: Thread Service 将内部解析异常转换为统一 error chunk。
        events = await self.collect_events(FakeAgent(events=(("values", None),)))

        self.assertEqual("error", events[-1]["status"])
        self.assertEqual("AttributeError", events[-1]["error_type"])

    async def test_agent_stream_error_yields_error_chunk(self) -> None:
        # FIXEME: 模型异常不再越过 Thread Service 直接抛给 Worker。
        events = await self.collect_events(
            FakeAgent(error=RuntimeError("model failed"))
        )

        self.assertEqual("error", events[-1]["status"])
        self.assertEqual("model failed", events[-1]["error"])
        self.assertEqual("RuntimeError", events[-1]["error_type"])

    async def test_resume_stream_passes_command_without_human_message(self) -> None:
        agent = FakeAgent()
        agent_item = SimpleNamespace(slug="test-agent")
        current_user = SimpleNamespace(uid="user-1")

        with (
            patch(
                "server.service.thread_service._build_agent_runtime",
                new_callable=AsyncMock,
                return_value=(agent_item, agent),
            ),
            patch(
                "server.service.thread_service._check_conv_status",
                new_callable=AsyncMock,
            ),
            patch(
                "server.service.thread_service.save_message_from_langgraph_state",
                new_callable=AsyncMock,
            ),
            patch(
                "server.service.thread_service.check_agent_interrupt_handler",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            events = [
                json.loads(chunk)
                async for chunk in thread_service.resume_agent_response(
                    agent_slug="test-agent",
                    thread_id="thread-1",
                    runtime_metadata={
                        "run_id": "resume-run",
                        "request_id": "resume-request",
                        "run_type": "resume",
                        "resume": {"answer": "PostgreSQL"},
                    },
                    current_user=current_user,
                    db=object(),
                )
            ]

        self.assertEqual("PostgreSQL", agent.resume_input.resume)
        self.assertEqual("finished", events[-1]["status"])

    async def test_resume_stream_error_yields_error_chunk(self) -> None:
        # FIXEME: Resume 入口使用自己的 builder 输出 error chunk。
        agent = FakeAgent(error=RuntimeError("resume failed"))
        agent_item = SimpleNamespace(slug="test-agent")
        current_user = SimpleNamespace(uid="user-1")

        with (
            patch(
                "server.service.thread_service._build_agent_runtime",
                new_callable=AsyncMock,
                return_value=(agent_item, agent),
            ),
            patch(
                "server.service.thread_service._check_conv_status",
                new_callable=AsyncMock,
            ),
        ):
            events = [
                json.loads(chunk)
                async for chunk in thread_service.resume_agent_response(
                    agent_slug="test-agent",
                    thread_id="thread-1",
                    runtime_metadata={
                        "run_id": "resume-run",
                        "request_id": "resume-request",
                        "run_type": "resume",
                        "resume": {"answer": "PostgreSQL"},
                    },
                    current_user=current_user,
                    db=object(),
                )
            ]

        self.assertEqual("error", events[-1]["status"])
        self.assertEqual("resume failed", events[-1]["error"])
        self.assertEqual("RuntimeError", events[-1]["error_type"])


if __name__ == "__main__":
    unittest.main()
