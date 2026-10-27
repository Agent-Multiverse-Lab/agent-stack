from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, MutableMapping
from dataclasses import replace
from typing import Annotated, Any, NotRequired, TypedDict, override

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


MAX_EXECUTE_OUTPUT_BYTES = 100_000


class SandboxRuntimeState(TypedDict):
    sandbox_id: str


def _replace_sandbox_state(
    current: SandboxRuntimeState | None,
    update: SandboxRuntimeState | None,
) -> SandboxRuntimeState | None:
    """并行工具可重复写入会话实例引用；新引用和结束时的 None 覆盖旧值。"""
    return update


class SandboxMiddlewareState(AgentState):
    sandbox: NotRequired[
        Annotated[SandboxRuntimeState | None, _replace_sandbox_state]
    ]


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
    def _ensure_sandbox(cls, runtime: object, provider) -> tuple[str, bool]:
        state = getattr(runtime, "state", None)
        current_id = cls._read_sandbox_id(state)
        uid, thread_id = cls._context_ids(runtime)
        context = getattr(runtime, "context", None)
        skill_root = context.get("skill_root") if isinstance(context, Mapping) else getattr(context, "skill_root", None)
        sandbox_id = provider.acquire(uid, thread_id, **({"skill_root": skill_root} if skill_root else {}))
        try:
            cls._write_sandbox_id(state, sandbox_id)
        except Exception:
            provider.release(sandbox_id)
            raise
        return sandbox_id, current_id != sandbox_id

    @classmethod
    async def _ensure_sandbox_async(cls, runtime: object, provider) -> tuple[str, bool]:
        state = getattr(runtime, "state", None)
        current_id = cls._read_sandbox_id(state)
        uid, thread_id = cls._context_ids(runtime)
        context = getattr(runtime, "context", None)
        skill_root = context.get("skill_root") if isinstance(context, Mapping) else getattr(context, "skill_root", None)
        sandbox_id = await provider.acquire_async(uid, thread_id, **({"skill_root": skill_root} if skill_root else {}))
        try:
            cls._write_sandbox_id(state, sandbox_id)
        except Exception:
            provider.release(sandbox_id)
            raise
        return sandbox_id, current_id != sandbox_id

    @staticmethod
    def _limit_execute_output(result):
        """Limit tool messages while preserving complete backend file responses."""
        if isinstance(result, ToolMessage) and isinstance(result.content, str):
            content = result.content.encode("utf-8")
            if len(content) > MAX_EXECUTE_OUTPUT_BYTES:
                return result.model_copy(update={"content": content[:MAX_EXECUTE_OUTPUT_BYTES].decode("utf-8", errors="ignore") + "\n[output truncated]"})
        if isinstance(result, Command) and isinstance(result.update, dict):
            messages = result.update.get("messages")
            if isinstance(messages, list):
                return replace(result, update={**result.update, "messages": [SandboxMiddleware._limit_execute_output(m) for m in messages]})
        return result

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

        provider = get_sandbox_provider()
        sandbox_id, acquired = self._ensure_sandbox(request.runtime, provider)
        try:
            result = handler(request)
        finally:
            provider.release(sandbox_id)
        if request.tool_call["name"] == "execute":
            result = self._limit_execute_output(result)
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

        provider = get_sandbox_provider()
        sandbox_id, acquired = await self._ensure_sandbox_async(request.runtime, provider)
        try:
            result = await handler(request)
        finally:
            provider.release(sandbox_id)
        if request.tool_call["name"] == "execute":
            result = self._limit_execute_output(result)
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
        return {"sandbox": None}


def create_sandbox_middleware() -> SandboxMiddleware:
    return SandboxMiddleware()
