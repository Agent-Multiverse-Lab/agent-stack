from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, MutableMapping
from dataclasses import replace
from typing import Any, NotRequired, TypedDict, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from src.agents.backends.sandbox import get_sandbox_provider

SANDBOX_TOOL_NAMES = frozenset(
    {
        "edit_file",
        "execute",
        "glob",
        "grep",
        "ls",
        "read_file",
        "write_file",
    }
)


class SandboxRuntimeState(TypedDict):
    sandbox_id: str


class SandboxMiddlewareState(AgentState):
    sandbox: NotRequired[SandboxRuntimeState | None]


class SandboxMiddleware(AgentMiddleware[SandboxMiddlewareState]):
    """按需获取沙箱，并把沙箱 ID 写入 Agent 运行状态。"""

    state_schema = SandboxMiddlewareState

    @staticmethod
    def _read_sandbox_id(state: object) -> str | None:
        if not isinstance(state, Mapping):
            return None
        sandbox = state.get("sandbox")
        if not isinstance(sandbox, Mapping):
            return None
        sandbox_id = sandbox.get("sandbox_id")
        if not isinstance(sandbox_id, str):
            return None
        normalized = sandbox_id.strip()
        return normalized or None

    @staticmethod
    def _write_sandbox_id(state: object, sandbox_id: str) -> None:
        if not isinstance(state, MutableMapping):
            raise RuntimeError("Agent 运行状态不可写，无法保存 sandbox_id。")
        state["sandbox"] = {"sandbox_id": sandbox_id}

    @staticmethod
    def _context_value(context: object, name: str) -> str:
        if isinstance(context, Mapping):
            value = context.get(name)
        else:
            value = getattr(context, name, None)
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f"SandboxMiddleware 缺少运行时参数：{name}")
        return normalized

    @classmethod
    def _context_ids(cls, runtime: object) -> tuple[str, str]:
        context = getattr(runtime, "context", None)
        return (
            cls._context_value(context, "uid"),
            cls._context_value(context, "thread_id"),
        )

    @staticmethod
    def _uses_sandbox(request: ToolCallRequest) -> bool:
        tool_name = request.tool_call.get("name")
        return isinstance(tool_name, str) and tool_name in SANDBOX_TOOL_NAMES

    @classmethod
    def _ensure_sandbox(cls, runtime: object) -> tuple[str, bool]:
        state = getattr(runtime, "state", None)
        provider = get_sandbox_provider()
        current_id = cls._read_sandbox_id(state)
        if current_id is not None and provider.get(current_id) is not None:
            return current_id, False

        uid, thread_id = cls._context_ids(runtime)
        sandbox_id = provider.acquire(uid, thread_id)
        cls._write_sandbox_id(state, sandbox_id)
        return sandbox_id, True

    @classmethod
    async def _ensure_sandbox_async(cls, runtime: object) -> tuple[str, bool]:
        state = getattr(runtime, "state", None)
        provider = get_sandbox_provider()
        current_id = cls._read_sandbox_id(state)
        if current_id is not None and provider.get(current_id) is not None:
            return current_id, False

        uid, thread_id = cls._context_ids(runtime)
        sandbox_id = await provider.acquire_async(uid, thread_id)
        cls._write_sandbox_id(state, sandbox_id)
        return sandbox_id, True

    @staticmethod
    def _attach_sandbox_update(
        result: ToolMessage | Command[Any],
        sandbox_id: str,
    ) -> ToolMessage | Command[Any]:
        sandbox_update = {"sandbox": {"sandbox_id": sandbox_id}}
        if isinstance(result, ToolMessage):
            return Command(
                update={
                    **sandbox_update,
                    "messages": [result],
                }
            )

        if isinstance(result.update, dict):
            return replace(
                result,
                update={
                    **result.update,
                    **sandbox_update,
                },
            )
        if result.update is None:
            return replace(result, update=sandbox_update)
        return result

    @override
    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        if not self._uses_sandbox(request):
            return handler(request)

        sandbox_id, acquired = self._ensure_sandbox(request.runtime)
        result = handler(request)
        if not acquired:
            return result
        return self._attach_sandbox_update(result, sandbox_id)

    @override
    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[
            [ToolCallRequest],
            Awaitable[ToolMessage | Command[Any]],
        ],
    ) -> ToolMessage | Command[Any]:
        if not self._uses_sandbox(request):
            return await handler(request)

        sandbox_id, acquired = await self._ensure_sandbox_async(request.runtime)
        result = await handler(request)
        if not acquired:
            return result
        return self._attach_sandbox_update(result, sandbox_id)

    @override
    def after_agent(
        self,
        state: SandboxMiddlewareState,
        runtime: Any,
    ) -> dict[str, Any] | None:
        sandbox_id = self._read_sandbox_id(state)
        if sandbox_id is None:
            return None
        get_sandbox_provider().release(sandbox_id)
        return {"sandbox": None}

    @override
    async def aafter_agent(
        self,
        state: SandboxMiddlewareState,
        runtime: Any,
    ) -> dict[str, Any] | None:
        sandbox_id = self._read_sandbox_id(state)
        if sandbox_id is None:
            return None
        await asyncio.to_thread(get_sandbox_provider().release, sandbox_id)
        return {"sandbox": None}


def create_sandbox_middleware() -> SandboxMiddleware:
    return SandboxMiddleware()
