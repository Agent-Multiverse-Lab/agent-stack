"""子 Run 可分配的工具目录和运行时工具装配。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.tools import BaseTool

from server.service.mcp_service import get_mcp_server_errors, get_mcp_tools, list_mcp_servers
from src.agents.backends.composite_backend import CustomFilesystemMiddleware, create_custom_filesystem_middleware
from src.agents.middlewares.image_validation_middleware import ImageValidationMiddleware
from src.knowledge.tools import knowledge_search, web_search
from src.third_party.satellite_gateway.tools import build_satellite_catalog_tools

if TYPE_CHECKING:
    from src.agents.buildin.subagents.subagent_context import SubAgentContext


def _tool_names(value: list[str] | None) -> list[str] | None:
    """保留显式空集合，并按首次出现的顺序去重。"""
    if value is None:
        return None
    if not isinstance(value, list) or any(not isinstance(name, str) or not name.strip() for name in value):
        raise ValueError("tools 必须是工具名称列表")
    return list(dict.fromkeys(value))


async def _load_tools(
    context: SubAgentContext,
    selected: list[str] | None,
) -> tuple[dict[str, BaseTool], set[str], CustomFilesystemMiddleware | None]:
    """本地工具按上下文构造，仅在需要远程工具时发现 MCP。"""
    if selected == []:
        return {}, set(), None

    filesystem = create_custom_filesystem_middleware(context=context)
    tools = {
        tool.name: tool
        for tool in (knowledge_search, web_search, *build_satellite_catalog_tools(context), *filesystem.tools)
    }
    mcp_tools = ()
    if selected is None or any(name not in tools for name in selected):
        mcp_tools = await get_mcp_tools(context.mcps)
        if selected is None and (context.require_mcp_tools or context.mcps):
            ImageValidationMiddleware.validate_mcp_tools(
                mcp_tools, context.mcps, list_mcp_servers(), get_mcp_server_errors()
            )
        for tool in mcp_tools:
            if tool.name in tools:
                raise ValueError(f"工具名称重复：{tool.name}")
            tools[tool.name] = tool

    if selected is not None:
        unknown = [name for name in selected if name not in tools]
        if unknown:
            raise ValueError(f"未找到可分配的工具：{', '.join(unknown)}")
    return tools, {tool.name for tool in mcp_tools}, filesystem


async def list_agent_tool_catalog(context: SubAgentContext) -> list[dict[str, str]]:
    """返回当前服务范围内可用于委派的工具名称和描述。"""
    tools, _, _ = await _load_tools(context, None)
    return [{"name": tool.name, "description": tool.description} for tool in tools.values()]


async def resolve_spawn_tools(context: SubAgentContext, requested: list[str] | None) -> list[str]:
    """校验本次分配，未提供时物化模板工具，旧模板保留原有能力。"""
    selected = _tool_names(context.tools if requested is None else requested)
    tools, _, _ = await _load_tools(context, selected)
    return list(tools) if selected is None else selected


async def build_subagent_tools(
    context: SubAgentContext,
) -> tuple[list[BaseTool], set[str], CustomFilesystemMiddleware | None]:
    """只注册本次分配的工具，包括文件系统中间件提供的工具。"""
    selected = _tool_names(context.tools)
    tools, mcp_names, filesystem = await _load_tools(context, selected)
    selected_names = set(tools) if selected is None else set(selected)
    filesystem_names = {tool.name for tool in filesystem.tools} if filesystem else set()
    if filesystem:
        filesystem.tools = [tool for tool in filesystem.tools if tool.name in selected_names]
        if not filesystem.tools:
            filesystem = None
    return (
        [tool for name, tool in tools.items() if name in selected_names and name not in filesystem_names],
        mcp_names & selected_names,
        filesystem,
    )
