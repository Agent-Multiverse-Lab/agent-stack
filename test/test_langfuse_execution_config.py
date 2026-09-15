import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from langchain.messages import HumanMessage
from langgraph.types import Command

from server.service import thread_service
from server.service.langfuse_service import with_langfuse_config
from src.agents.base_agent import BaseAgent


class _EventStream:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


class _Graph:
    def __init__(self) -> None:
        self.calls = []

    async def astream_events(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return _EventStream()


class _Context(SimpleNamespace):
    def __init__(self):
        super().__init__(thread_id="", uid="")

    def update_context(self, values):
        self.__dict__.update(values)


class _Agent(BaseAgent):
    agent_context = _Context

    def __init__(self, graph):
        self.graph = graph

    async def get_agent(self, _context):
        return self.graph


class _ThreadAgent:
    agent_context = _Context

    def __init__(self) -> None:
        self.stream_kwargs = None
        self.resume_kwargs = None

    async def get_agent(self, _context):
        return SimpleNamespace(aget_state=AsyncMock(return_value=SimpleNamespace()))

    async def stream_messages_with_event(self, *_args, **kwargs):
        self.stream_kwargs = kwargs
        yield "messages", (
            {
                "event": "content-block-delta",
                "index": 0,
                "delta": {"type": "text-delta", "text": "ok"},
            },
            {"run_id": "model-run"},
        )

    async def stream_message_by_resume(self, *_args, **kwargs):
        self.resume_kwargs = kwargs
        yield "messages", (
            {
                "event": "content-block-delta",
                "index": 0,
                "delta": {"type": "text-delta", "text": "resumed"},
            },
            {"run_id": "model-run"},
        )


class LangfuseExecutionConfigTest(unittest.IsolatedAsyncioTestCase):
    async def test_chat_and_resume_put_trace_values_in_runnable_config(self):
        callbacks = [object()]
        metadata = {"run_id": "run-1"}
        tags = ["chat", "LeaderAgent"]

        for method, graph_input in (
            ("stream_messages_with_event", ["hello"]),
            ("stream_message_by_resume", Command(resume={"answer": "yes"})),
        ):
            with self.subTest(method=method):
                graph = _Graph()
                agent = _Agent(graph)
                stream = getattr(agent, method)(
                    graph_input,
                    runtime_context={"thread_id": "thread-1", "uid": "user-1"},
                    callbacks=callbacks,
                    metadata=metadata,
                    tags=tags,
                )
                async for _ in stream:
                    pass

                config = graph.calls[0][1]["config"]
                self.assertEqual(
                    {"thread_id": "thread-1", "uid": "user-1"},
                    config["configurable"],
                )
                self.assertEqual(callbacks, config["callbacks"])
                self.assertEqual(metadata, config["metadata"])
                self.assertEqual(tags, config["tags"])

    def test_disabled_langfuse_keeps_metadata_without_callbacks(self):
        with patch(
            "server.service.langfuse_service.get_langfuse_handler",
            return_value=None,
        ):
            config = with_langfuse_config(
                user_id="user-1",
                conversation_id="thread-1",
                agent_id="LeaderAgent",
                user_message_id="message-1",
                message_type="text",
                attachment_count=0,
                request_config={"run_id": "run-1"},
            )

        self.assertNotIn("callbacks", config)
        self.assertEqual("user-1", config["metadata"]["langfuse_user_id"])
        self.assertEqual("thread-1", config["metadata"]["langfuse_session_id"])
        self.assertEqual(["chat", "LeaderAgent"], config["tags"])

    async def test_thread_service_passes_langfuse_config_to_chat_stream(self):
        agent = _ThreadAgent()
        langfuse_config = {
            "callbacks": [object()],
            "metadata": {"run_id": "run-1"},
            "tags": ["chat", "LeaderAgent"],
        }
        input_message = SimpleNamespace(
            content="hello",
            image_content=None,
            msg_type="text",
            msg_metadata={"attachment_file_ids": ["file-1"]},
            langchain_msg=HumanMessage(content="hello"),
        )

        with (
            patch.object(
                thread_service,
                "_build_agent_runtime",
                AsyncMock(return_value=(SimpleNamespace(slug="LeaderAgent"), agent)),
            ),
            patch.object(thread_service, "_check_conv_status", AsyncMock()),
            patch.object(
                thread_service,
                "with_langfuse_config",
                return_value=langfuse_config,
            ) as build_config,
        ):
            stream = thread_service.stream_agent_response(
                agent_slug="LeaderAgent",
                thread_id="thread-1",
                runtime_metadata={
                    "run_id": "run-1",
                    "request_id": "request-1",
                    "trigger_message_id": "42",
                },
                thread_input_message=input_message,
                current_user=SimpleNamespace(uid="user-1"),
                db=SimpleNamespace(),
            )
            try:
                await anext(stream)
            finally:
                await stream.aclose()

        self.assertEqual(langfuse_config, {
            key: agent.stream_kwargs[key] for key in langfuse_config
        })
        build_config.assert_called_once_with(
            user_id="user-1",
            conversation_id="thread-1",
            agent_id="LeaderAgent",
            user_message_id="42",
            message_type="text",
            attachment_count=1,
            request_config={
                "run_id": "run-1",
                "request_id": "request-1",
                "run_type": "chat",
            },
        )

    async def test_thread_service_passes_langfuse_config_to_resume_stream(self):
        agent = _ThreadAgent()
        langfuse_config = {
            "callbacks": [object()],
            "metadata": {"run_id": "resume-run"},
            "tags": ["chat", "LeaderAgent"],
        }

        with (
            patch.object(thread_service, "_require_thread", AsyncMock()),
            patch.object(thread_service.agent_manager, "get_agent", return_value=agent),
            patch.object(thread_service, "_reslove_agent_interrupt", return_value=object()),
            patch.object(
                thread_service,
                "with_langfuse_config",
                return_value=langfuse_config,
            ) as build_config,
        ):
            stream = thread_service.resume_agent_response(
                resume_input={"question-1": "continue"},
                thread_id="thread-1",
                runtime_metadata={
                    "run_id": "resume-run",
                    "request_id": "resume-request",
                    "agent_slug": "LeaderAgent",
                },
                current_user=SimpleNamespace(uid="user-1"),
                db=SimpleNamespace(),
            )
            try:
                await anext(stream)
            finally:
                await stream.aclose()

        self.assertEqual(langfuse_config, {
            key: agent.resume_kwargs[key] for key in langfuse_config
        })
        build_config.assert_called_once_with(
            user_id="user-1",
            conversation_id="thread-1",
            agent_id="LeaderAgent",
            user_message_id="resume-request",
            message_type="resume",
            attachment_count=0,
            request_config={
                "run_id": "resume-run",
                "request_id": "resume-request",
                "run_type": "resume",
            },
        )


if __name__ == "__main__":
    unittest.main()
