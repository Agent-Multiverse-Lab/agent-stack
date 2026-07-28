from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from datetime import timedelta
from typing import Any, cast

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.interceptors import (
    MCPToolCallRequest,
    MCPToolCallResult,
)
from langchain_mcp_adapters.sessions import Connection

from src.configs import config
from src.utils import logger

_CONNECT_TIMEOUT_SECONDS = float(config.mcp_connect_timeout_seconds)
_TOOL_CALL_TIMEOUT_SECONDS = float(config.mcp_tool_call_timeout_seconds)


def _build_connection(raw: dict[str, Any]) -> Connection:
    """把一个远程 MCP Server 配置转换成 Adapter 配置。"""

    transport = str(raw.get("transport", raw.get("type", "streamable_http"))).replace("-", "_")
    if transport == "http":
        transport = "streamable_http"
    if transport == "stdio":
        raise ValueError("MCP Server 由外部常驻服务管理，不支持由后端启动 stdio 子进程")

    allowed_fields = {
        "sse": ("url", "headers", "timeout", "sse_read_timeout"),
        "streamable_http": (
            "url",
            "headers",
            "timeout",
            "sse_read_timeout",
            "terminate_on_close",
        ),
        "websocket": ("url",),
    }.get(transport)
    if allowed_fields is None:
        raise ValueError(f"不支持的 MCP transport：{transport}")
    if not raw.get("url"):
        raise ValueError(f"{transport} MCP Server 必须配置 url")

    connection: dict[str, Any] = {
        "transport": transport,
        **{name: raw[name] for name in allowed_fields if raw.get(name) is not None},
    }
    session_kwargs = dict(raw.get("session_kwargs") or {})
    session_kwargs.setdefault(
        "read_timeout_seconds",
        timedelta(seconds=_TOOL_CALL_TIMEOUT_SECONDS),
    )
    connection["session_kwargs"] = session_kwargs
    return cast(Connection, connection)


def _build_connections() -> tuple[dict[str, Connection], dict[str, str]]:
    """读取项目配置，忽略禁用或无效的 Server。"""

    connections: dict[str, Connection] = {}
    errors: dict[str, str] = {}
    for server_name, raw in config.mcp_servers.items():
        if raw.get("enabled", True) is False:
            continue
        try:
            connections[server_name] = _build_connection(raw)
        except Exception as exc:
            errors[server_name] = f"{type(exc).__name__}: {exc}"
    return connections, errors


_CONNECTIONS, _CONFIG_ERRORS = _build_connections()
_SERVER_ERRORS = dict(_CONFIG_ERRORS)
_TOOLS: dict[str, BaseTool] = {}
_TOOL_ROUTES: dict[str, tuple[str, str]] = {}
_TOOLS_LOADED = False
_TOOLS_LOCK = asyncio.Lock()
_CALL_SEMAPHORE = asyncio.Semaphore(config.mcp_max_concurrency)


async def _intercept_tool_call(
    request: MCPToolCallRequest,
    handler: Callable[
        [MCPToolCallRequest],
        Awaitable[MCPToolCallResult],
    ],
) -> MCPToolCallResult:
    """限制直接交给 Agent 的 MCP 工具并发和调用时间。"""

    try:
        async with _CALL_SEMAPHORE:
            async with asyncio.timeout(_TOOL_CALL_TIMEOUT_SECONDS):
                result = await handler(request)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        _SERVER_ERRORS[request.server_name] = f"{type(exc).__name__}: {exc}"
        raise

    _SERVER_ERRORS.pop(request.server_name, None)
    return result


def get_mcp_client() -> MultiServerMCPClient:
    """创建一个 LangChain MCP Adapter 客户端。"""

    return MultiServerMCPClient(
        _CONNECTIONS,
        tool_interceptors=[_intercept_tool_call],
        tool_name_prefix=True,
    )


def list_mcp_servers() -> tuple[str, ...]:
    """列出已经配置并启用的 MCP Server。"""

    return tuple(sorted(_CONNECTIONS))


def get_mcp_server_errors() -> dict[str, str]:
    """返回最近一次工具发现或调用产生的 Server 错误。"""

    return dict(_SERVER_ERRORS)


async def get_mcp_tools(
    server_names: Sequence[str] | None = None,
) -> tuple[BaseTool, ...]:
    """按 Server 名称获取 MCP 工具；首次调用时自动发现并缓存。"""

    async with _TOOLS_LOCK:
        if not _TOOLS_LOADED:
            await _reload_mcp_tools()

        selected_servers = {
            str(server_name).strip()
            for server_name in server_names or ()
            if str(server_name).strip()
        }
        tools = (
            tool
            for tool_name, tool in _TOOLS.items()
            if (
                not selected_servers
                or _TOOL_ROUTES[tool_name][0] in selected_servers
            )
        )
        return tuple(sorted(tools, key=lambda tool: tool.name))


async def refresh_mcp_tools() -> tuple[BaseTool, ...]:
    """重新发现全部 MCP 工具。"""

    async with _TOOLS_LOCK:
        await _reload_mcp_tools()
        return tuple(sorted(_TOOLS.values(), key=lambda tool: tool.name))


async def get_mcp_tool(tool_name: str) -> BaseTool | None:
    """按 Adapter 生成的完整名称获取工具。"""

    await get_mcp_tools()
    return _TOOLS.get(tool_name)


async def call_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> Any:
    """直接调用 MCP 工具并保留原始 MCP 结果。"""

    if await get_mcp_tool(tool_name) is None:
        raise KeyError(f"MCP 工具不存在：{tool_name}")
    server_name, original_tool_name = _TOOL_ROUTES[tool_name]

    try:
        async with _CALL_SEMAPHORE:
            async with asyncio.timeout(_TOOL_CALL_TIMEOUT_SECONDS):
                async with get_mcp_client().session(server_name) as session:
                    result = await session.call_tool(
                        original_tool_name,
                        dict(arguments or {}),
                        read_timeout_seconds=timedelta(seconds=_TOOL_CALL_TIMEOUT_SECONDS),
                    )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        _SERVER_ERRORS[server_name] = error
        raise RuntimeError(f"MCP 工具调用失败：{tool_name}；{error}") from exc

    _SERVER_ERRORS.pop(server_name, None)
    return result


async def _load_server_tools(
    server_name: str,
) -> tuple[str, tuple[BaseTool, ...], str | None]:
    """发现一个 MCP Server 的工具。"""

    try:
        async with asyncio.timeout(_CONNECT_TIMEOUT_SECONDS):
            tools = await get_mcp_client().get_tools(server_name=server_name)
        return server_name, tuple(tools), None
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        return server_name, (), f"{type(exc).__name__}: {exc}"


async def _reload_mcp_tools() -> None:
    """并行发现工具，并隔离单个 Server 的失败。"""

    global _TOOLS, _TOOL_ROUTES, _TOOLS_LOADED

    results = await asyncio.gather(*(_load_server_tools(name) for name in _CONNECTIONS))
    tools: dict[str, BaseTool] = {}
    routes: dict[str, tuple[str, str]] = {}
    errors = dict(_CONFIG_ERRORS)
    loaded_server_count = 0

    for server_name, loaded_tools, error in results:
        if error is not None:
            errors[server_name] = error
            continue

        loaded_server_count += 1
        prefix = f"{server_name}_"
        for tool in loaded_tools:
            if tool.name in tools or not tool.name.startswith(prefix):
                errors[server_name] = f"MCP 工具完整名称冲突：{tool.name}"
                continue
            tools[tool.name] = tool
            routes[tool.name] = (server_name, tool.name[len(prefix) :])

    _TOOLS = tools
    _TOOL_ROUTES = routes
    _SERVER_ERRORS.clear()
    _SERVER_ERRORS.update(errors)
    _TOOLS_LOADED = True
    logger.info(
        "MCP 工具加载完成：servers=%s, tools=%s, failed=%s",
        loaded_server_count,
        len(_TOOLS),
        len(_SERVER_ERRORS),
    )
