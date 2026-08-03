from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from langchain_core.messages import ToolMessage
from langgraph.types import Command

_MODULE_NAME = "_sandbox_middleware_test_module"
_MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "agents"
    / "middlewares"
    / "sandbox_middleware.py"
)
_sandbox_package = types.ModuleType("src.agents.backends.sandbox")
_sandbox_package.get_sandbox_provider = lambda: None

_spec = importlib.util.spec_from_file_location(_MODULE_NAME, _MODULE_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("无法加载 sandbox_middleware.py")
_sandbox_middleware = importlib.util.module_from_spec(_spec)
with mock.patch.dict(
    sys.modules,
    {
        _MODULE_NAME: _sandbox_middleware,
        "src.agents.backends.sandbox": _sandbox_package,
    },
):
    _spec.loader.exec_module(_sandbox_middleware)

SandboxMiddleware = _sandbox_middleware.SandboxMiddleware


@dataclass
class FakeContext:
    uid: str = "user-1"
    thread_id: str = "thread-1"


class FakeProvider:
    def __init__(self) -> None:
        self.sandboxes: dict[str, object] = {}
        self.acquire_calls: list[tuple[str, str]] = []
        self.release_calls: list[str] = []

    def acquire(self, uid: str, thread_id: str) -> str:
        self.acquire_calls.append((uid, thread_id))
        sandbox_id = f"{uid}:{thread_id}"
        self.sandboxes[sandbox_id] = object()
        return sandbox_id

    async def acquire_async(self, uid: str, thread_id: str) -> str:
        return self.acquire(uid, thread_id)

    def get(self, sandbox_id: str) -> object | None:
        return self.sandboxes.get(sandbox_id)

    def release(self, sandbox_id: str) -> bool:
        self.release_calls.append(sandbox_id)
        return self.sandboxes.pop(sandbox_id, None) is not None


def make_request(tool_name: str, state: dict | None = None):
    runtime = SimpleNamespace(
        state={} if state is None else state,
        context=FakeContext(),
    )
    return SimpleNamespace(
        tool_call={"name": tool_name},
        runtime=runtime,
    )


def make_tool_message() -> ToolMessage:
    return ToolMessage(
        content="ok",
        tool_call_id="tool-call-1",
    )


class SandboxMiddlewareTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.middleware = SandboxMiddleware()
        self.provider = FakeProvider()
        self.provider_patch = mock.patch.object(
            _sandbox_middleware,
            "get_sandbox_provider",
            return_value=self.provider,
        )
        self.provider_patch.start()

    def tearDown(self) -> None:
        self.provider_patch.stop()

    def test_sync_tool_call_acquires_before_handler_and_persists_state(self) -> None:
        request = make_request("read_file")
        state_seen_by_handler: list[dict] = []

        def handler(current_request):
            state_seen_by_handler.append(dict(current_request.runtime.state))
            return make_tool_message()

        result = self.middleware.wrap_tool_call(request, handler)

        self.assertIsInstance(result, Command)
        self.assertEqual(
            request.runtime.state,
            {"sandbox": {"sandbox_id": "user-1:thread-1"}},
        )
        self.assertEqual(state_seen_by_handler, [request.runtime.state])
        self.assertEqual(
            result.update["sandbox"],
            {"sandbox_id": "user-1:thread-1"},
        )
        self.assertEqual(self.provider.acquire_calls, [("user-1", "thread-1")])

    def test_existing_sandbox_is_reused(self) -> None:
        sandbox_id = self.provider.acquire("user-1", "thread-1")
        request = make_request(
            "execute",
            {"sandbox": {"sandbox_id": sandbox_id}},
        )

        result = self.middleware.wrap_tool_call(
            request,
            lambda _request: make_tool_message(),
        )

        self.assertIsInstance(result, ToolMessage)
        self.assertEqual(self.provider.acquire_calls, [("user-1", "thread-1")])

    def test_non_sandbox_tool_does_not_acquire(self) -> None:
        request = make_request("web_search")

        result = self.middleware.wrap_tool_call(
            request,
            lambda _request: make_tool_message(),
        )

        self.assertIsInstance(result, ToolMessage)
        self.assertEqual(self.provider.acquire_calls, [])
        self.assertEqual(request.runtime.state, {})

    async def test_async_tool_call_acquires_and_after_agent_releases(self) -> None:
        request = make_request("write_file")

        async def handler(_request):
            return make_tool_message()

        result = await self.middleware.awrap_tool_call(request, handler)
        update = await self.middleware.aafter_agent(
            request.runtime.state,
            request.runtime,
        )

        self.assertIsInstance(result, Command)
        self.assertEqual(update, {"sandbox": None})
        self.assertEqual(self.provider.release_calls, ["user-1:thread-1"])


if __name__ == "__main__":
    unittest.main()
