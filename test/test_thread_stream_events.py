import asyncio
import json
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from langchain.messages import HumanMessage
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from langgraph.types import Command

from server.service import thread_service
from src.agents.buildin.subagents import SubAgentContext


async def no_interrupt(**kwargs):
    return
    yield


@asynccontextmanager
async def fake_session():
    yield object()


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
        self.runtime_context = _kwargs["runtime_context"]
        if self.error is not None:
            raise self.error
        for event in self.events:
            yield event

    async def stream_message_by_resume(self, resume_input, **_kwargs):
        self.resume_input = resume_input
        self.runtime_context = _kwargs["runtime_context"]
        if self.error is not None:
            raise self.error
        for event in self.events:
            yield event

    async def get_agent(self, context):
        return SimpleNamespace(aget_state=AsyncMock(return_value=SimpleNamespace(tasks=(SimpleNamespace(interrupts=(object(),)),))))


class ThreadStreamEventTest(unittest.IsolatedAsyncioTestCase):
    async def test_build_agent_runtime_looks_up_uuid_thread_for_user(self):
        thread_id = "b2308e62-68a3-433e-b051-7e0c218a9249"
        conversation_repository = SimpleNamespace(
            get_conversation_by_thread_id_for_user=AsyncMock(
                return_value=SimpleNamespace(
                    uid="user-1",
                    conversation_metadata={},
                )
            )
        )
        agent_item = SimpleNamespace(
            slug="test-agent",
            backend_id="SubAgentGraph",
            name="测试角色",
            description="test",
            agent_config={},
            role="subagent",
            is_subagent=True,
        )
        agent_repository = SimpleNamespace(get_by_slug_for_run_type=AsyncMock(return_value=agent_item))
        agent_instance = object()
        db = object()

        with (
            patch(
                "server.service.thread_service.ConversationRepository",
                return_value=conversation_repository,
            ),
            patch(
                "server.service.thread_service.AgentRepository",
                return_value=agent_repository,
            ),
            patch.object(
                thread_service.agent,
                "get_agent_class",
                return_value=Mock(agent_context=SubAgentContext, return_value=agent_instance),
            ) as resolve_class,
        ):
            result = await thread_service._build_agent_runtime(
                agent_slug="test-agent",
                user=SimpleNamespace(uid="user-1"),
                thread_id=thread_id,
                db=db,
            )

        self.assertEqual((agent_item, agent_instance, "dashscope/qwen3.8-max"), result)
        resolve_class.assert_called_once_with(agent_item.backend_id)
        resolve_class.return_value.assert_called_once_with()
        conversation_repository.get_conversation_by_thread_id_for_user.assert_awaited_once_with(
            thread_id=thread_id,
            user_id="user-1",
        )

    async def test_runtime_context_includes_selected_model(self):
        context = await thread_service._build_agent_runtime_context(
            uid="user-1",
            run_id="run-1",
            thread_id="thread-1",
            request_id="request-1",
            model="dashscope/qwen3.8-max",
        )

        self.assertEqual("dashscope/qwen3.8-max", context["model"])

    async def collect_events(self, agent: FakeAgent, *, conversation_metadata=None) -> list[dict]:
        agent_item = SimpleNamespace(slug="test-agent", agent_config={"model": "dashscope/qwen3.8-max"})
        model_id = thread_service.resolve_chat_model_selection(
            conversation_model=(conversation_metadata or {}).get("model"),
            agent_model=agent_item.agent_config["model"],
        )
        input_message = SimpleNamespace(
            content="hello",
            image_content=None,
            msg_type="text",
            msg_metadata={"attachment_file_ids": []},
            langchain_msg=HumanMessage(content="hello"),
        )
        current_user = SimpleNamespace(uid="user-1")
        save_messages = AsyncMock()
        self.save_messages = save_messages

        with (
            patch(
                "server.service.thread_service._build_agent_runtime",
                new_callable=AsyncMock,
                return_value=(agent_item, agent, model_id),
            ),
            patch(
                "server.service.thread_service.ConversationRepository",
                return_value=object(),
            ),
            patch(
                "server.service.thread_service._check_conv_status",
                new_callable=AsyncMock,
                return_value=SimpleNamespace(conversation_metadata=conversation_metadata or {}),
            ),
            patch(
                "server.service.thread_service.save_message_from_langgraph_state",
                new=save_messages,
            ),
            # FIXEME: 流事件单测不重复验证 checkpoint interrupt fixture。
            patch(
                "server.service.thread_service.check_agent_interrupt_handler",
                new=no_interrupt,
            ),
            patch.object(thread_service.postgres_manager, "get_async_session_context", fake_session),
            patch.object(thread_service, "save_partial_message", AsyncMock()),
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
                        "worker_id": "worker-1",
                    },
                    thread_input_message=input_message,
                    current_user=current_user,
                    db=object(),
                )
            ]

    async def test_stream_error_saves_partial_message(self) -> None:
        class PartialAgent:
            agent_context = FakeContext

            async def stream_messages_with_event(self, *_args, **_kwargs):
                yield (
                    "messages",
                    (
                        {
                            "event": "content-block-delta",
                            "index": 0,
                            "delta": {"type": "text-delta", "text": "半句"},
                        },
                        {"run_id": "model-run-1"},
                    ),
                )
                raise RuntimeError("stream boom")

        with (
            patch.object(
                thread_service, "_build_agent_runtime",
                AsyncMock(return_value=(
                    SimpleNamespace(slug="test-agent", agent_config={}),
                    PartialAgent(),
                    "dashscope/qwen3.8-max",
                )),
            ),
            patch.object(
                thread_service, "_check_conv_status",
                AsyncMock(return_value=SimpleNamespace(conversation_metadata={})),
            ),
            patch.object(thread_service, "check_agent_interrupt_handler", new=no_interrupt),
            patch.object(thread_service.postgres_manager, "get_async_session_context", fake_session),
            patch.object(thread_service, "save_partial_message", AsyncMock()) as partial,
        ):
            events = [
                json.loads(chunk)
                async for chunk in thread_service.stream_agent_response(
                    agent_slug="test-agent",
                    thread_id="thread-1",
                    runtime_metadata={
                        "run_id": "run-1",
                        "request_id": "request-1",
                        "thread_id": "thread-1",
                        "worker_id": "worker-1",
                    },
                    thread_input_message=SimpleNamespace(
                        content="hello",
                        image_content=None,
                        msg_type="text",
                        msg_metadata={"attachment_file_ids": []},
                        langchain_msg=HumanMessage(content="hello"),
                    ),
                    current_user=SimpleNamespace(uid="user-1"),
                    db=object(),
                )
            ]

        self.assertEqual("error", events[-1]["status"])
        self.assertEqual("Error streaming messages: stream boom", events[-1]["error"])
        self.assertEqual("unexpected_error", events[-1]["error_type"])
        kwargs = partial.await_args.kwargs
        self.assertEqual("半句", kwargs["full_msg"].content)
        self.assertEqual("unexpected_error", kwargs["error_type"])
        self.assertEqual("run-1", kwargs["run_id"])

    async def test_stream_cancel_saves_partial_message(self) -> None:
        started = asyncio.Event()

        class BlockingAgent:
            agent_context = FakeContext

            async def stream_messages_with_event(self, *_args, **_kwargs):
                yield (
                    "messages",
                    (
                        {
                            "event": "content-block-delta",
                            "index": 0,
                            "delta": {"type": "text-delta", "text": "半句"},
                        },
                        {"run_id": "model-run-1"},
                    ),
                )
                started.set()
                await asyncio.Event().wait()

        async def consume():
            async for _chunk in thread_service.stream_agent_response(
                agent_slug="test-agent",
                thread_id="thread-1",
                runtime_metadata={
                    "run_id": "run-1",
                    "request_id": "request-1",
                    "thread_id": "thread-1",
                    "worker_id": "worker-1",
                },
                thread_input_message=SimpleNamespace(
                    content="hello",
                    image_content=None,
                    msg_type="text",
                    msg_metadata={"attachment_file_ids": []},
                    langchain_msg=HumanMessage(content="hello"),
                ),
                current_user=SimpleNamespace(uid="user-1"),
                db=object(),
            ):
                pass

        with (
            patch.object(
                thread_service, "_build_agent_runtime",
                AsyncMock(return_value=(
                    SimpleNamespace(slug="test-agent", agent_config={}),
                    BlockingAgent(),
                    "dashscope/qwen3.8-max",
                )),
            ),
            patch.object(
                thread_service, "_check_conv_status",
                AsyncMock(return_value=SimpleNamespace(conversation_metadata={})),
            ),
            patch.object(thread_service, "check_agent_interrupt_handler", new=no_interrupt),
            patch.object(thread_service.postgres_manager, "get_async_session_context", fake_session),
            patch.object(thread_service, "save_partial_message", AsyncMock()) as partial,
        ):
            task = asyncio.create_task(consume())
            await asyncio.wait_for(started.wait(), timeout=5)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        kwargs = partial.await_args.kwargs
        self.assertEqual("半句", kwargs["full_msg"].content)
        self.assertEqual("interrupted", kwargs["error_type"])
        self.assertEqual("run-1", kwargs["run_id"])

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

    async def test_v3_tool_call_populates_loading_stream_event(self) -> None:
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
                                "event": "content-block-finish",
                                "index": 0,
                                "content": {
                                    "type": "tool_call",
                                    "id": "call-1",
                                    "name": "search",
                                    "args": {"query": "agent events"},
                                },
                            },
                            metadata,
                        ),
                    ),
                )
            )
        )

        loading = [event for event in events if event["status"] == "loading"]
        self.assertEqual(1, len(loading))
        self.assertEqual(
            {
                "type": "tool_call",
                "message_id": "message-1",
                "thread_id": "thread-1",
                "tool_call_id": "call-1",
                "name": "search",
                "args": {"query": "agent events"},
                "index": 0,
            },
            loading[0]["stream_event"][0],
        )

    async def test_v2_messages_and_empty_chunks_do_not_abort_stream(self):
        for message in (AIMessage(content="OK"), AIMessageChunk(content="OK"), AIMessageChunk(content="")):
            with self.subTest(message=message):
                events = await self.collect_events(FakeAgent(events=(("messages", (message, {})),)))
                self.assertEqual(events[-1]["status"], "finished")
                loading = [event for event in events if event["status"] == "loading"]
                self.assertEqual([event["response"] for event in loading], ["OK"] if message.content else [])
    async def test_invalid_values_payload_yields_error_chunk(self) -> None:
        # FIXEME: Thread Service 将内部解析异常转换为统一 error chunk。
        events = await self.collect_events(FakeAgent(events=(("values", None),)))

        self.assertEqual("error", events[-1]["status"])
        self.assertEqual("unexpected_error", events[-1]["error_type"])

    async def test_subagent_command_result_can_be_sent_as_json(self):
        command = Command(update={"messages": [ToolMessage(content="child result", tool_call_id="task-1")]})
        events = await self.collect_events(
            FakeAgent(
                events=(
                    (
                        "agent_execute_event",
                        {
                            "stream_namesapce": [],
                            "stream_data": {"event": "tool-completed", "output": command},
                        },
                    ),
                )
            )
        )
        output = events[0]["event"]["stream_data"]["output"]
        self.assertEqual(output["update"]["messages"][0]["content"], "child result")
        self.assertEqual(events[-1]["status"], "finished")

    async def test_agent_stream_error_yields_error_chunk(self) -> None:
        # FIXEME: 模型异常不再越过 Thread Service 直接抛给 Worker。
        events = await self.collect_events(FakeAgent(error=RuntimeError("model failed")))

        self.assertEqual("error", events[-1]["status"])
        self.assertEqual("Error streaming messages: model failed", events[-1]["error"])
        self.assertEqual("unexpected_error", events[-1]["error_type"])

    async def test_chat_stream_loads_bound_model_into_runtime_context(self):
        agent = FakeAgent()
        await self.collect_events(agent, conversation_metadata={"model": "deepseek/deepseek-v4-flash"})
        self.assertEqual(agent.runtime_context["model"], "deepseek/deepseek-v4-flash")

    async def test_resume_stream_passes_command_without_human_message(self) -> None:
        agent = FakeAgent()
        agent_item = SimpleNamespace(slug="test-agent", agent_config={})
        current_user = SimpleNamespace(uid="user-1")

        with (
            patch(
                "server.service.thread_service._build_agent_runtime",
                new_callable=AsyncMock,
                return_value=(agent_item, agent, "dashscope/qwen3.8-max"),
            ),
            patch(
                "server.service.thread_service._check_conv_status",
                new_callable=AsyncMock,
                return_value=SimpleNamespace(conversation_metadata={}),
            ),
            patch(
                "server.service.thread_service.save_message_from_langgraph_state",
                new_callable=AsyncMock,
            ),
            patch(
                "server.service.thread_service.check_agent_interrupt_handler",
                new=no_interrupt,
            ),
            patch.object(thread_service, "_require_thread", AsyncMock(return_value=SimpleNamespace(conversation_metadata={"model": "deepseek/deepseek-v4-flash"}))),
        ):
            events = [
                json.loads(chunk)
                async for chunk in thread_service.resume_agent_response(
                    resume_input={"answer": "PostgreSQL"},
                    thread_id="thread-1",
                    runtime_metadata={
                        "run_id": "resume-run",
                        "request_id": "resume-request",
                        "model": "dashscope/qwen3.8-max",
                        "worker_id": "worker-1",
                        "run_type": "resume",
                        "resume": {"answer": "PostgreSQL"},
                    },
                    current_user=current_user,
                    db=object(),
                )
            ]

        self.assertEqual({"answer": "PostgreSQL"}, agent.resume_input.resume)
        self.assertEqual("finished", events[-1]["status"])
        self.assertEqual(agent.runtime_context["model"], "dashscope/qwen3.8-max")

    async def test_resume_stream_error_yields_error_chunk(self) -> None:
        # FIXEME: Resume 入口使用自己的 builder 输出 error chunk。
        agent = FakeAgent(error=RuntimeError("resume failed"))
        agent_item = SimpleNamespace(slug="test-agent", agent_config={})
        current_user = SimpleNamespace(uid="user-1")

        with (
            patch(
                "server.service.thread_service._build_agent_runtime",
                new_callable=AsyncMock,
                return_value=(agent_item, agent, "dashscope/qwen3.8-max"),
            ),
            patch(
                "server.service.thread_service._check_conv_status",
                new_callable=AsyncMock,
                return_value=SimpleNamespace(conversation_metadata={}),
            ),
            patch.object(thread_service, "_require_thread", AsyncMock(return_value=SimpleNamespace(conversation_metadata={}))),
            patch.object(thread_service.postgres_manager, "get_async_session_context", fake_session),
            patch.object(thread_service, "save_partial_message", AsyncMock()),
        ):
            events = [
                json.loads(chunk)
                async for chunk in thread_service.resume_agent_response(
                    resume_input={"answer": "PostgreSQL"},
                    thread_id="thread-1",
                    runtime_metadata={
                        "run_id": "resume-run",
                        "request_id": "resume-request",
                        "worker_id": "worker-1",
                        "run_type": "resume",
                        "resume": {"answer": "PostgreSQL"},
                    },
                    current_user=current_user,
                    db=object(),
                )
            ]

        self.assertEqual("error", events[-1]["status"])
        self.assertEqual("Error during resume: resume failed", events[-1]["error"])
        self.assertEqual("resume_error", events[-1]["error_type"])


if __name__ == "__main__":
    unittest.main()
