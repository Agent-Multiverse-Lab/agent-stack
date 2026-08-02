"""
基于 deepagent 的 backend 以及 filesystem 构建通往 sandbox 的路径。

CompositeBackend 用虚拟路径前缀做路由，各 backend 路径直接来自运行时 context。
"""
from __future__ import annotations

from pathlib import Path

from deepagents.backends import CompositeBackend, FilesystemBackend
from deepagents.middleware.filesystem import FilesystemMiddleware
from langchain.tools import ToolRuntime

from src.agents.backends.memories_backend import UserMemoriesBackend
from src.agents.backends.sandbox import S2CSandbox
from src.agents.base_context import BaseContext
from src.configs.config import config as sys_config

EVICT_TOOL_EXEMPT = {"read_file"}  # read_file 的长结果直接返回，避免落入部分 backend

# Agent 可见的虚拟路径前缀（Composite 路由 key，建议以 / 结尾）
ROUTE_SKILL = "/skill/"
ROUTE_MEMORY = "/memory/"
ROUTE_WORKSPACE = "/workspace/"


def create_composite_backend(runtime: ToolRuntime) -> CompositeBackend:
    """从 deepagents 绑定的运行时 context 构建 CompositeBackend。"""
    context: BaseContext = runtime.context
    skill_root = Path(
        context.skill_root or Path(sys_config.save_dir) / "skills"
    ).resolve()
    workspace_root = (
        Path(sys_config.save_dir) / "workspaces" / context.uid / context.thread_id
    ).resolve()

    return CompositeBackend(
        default=S2CSandbox(thread_id=context.thread_id, uid=context.uid),
        routes={
            ROUTE_SKILL: FilesystemBackend(
                root_dir=str(skill_root),
                virtual_mode=True,
            ),
            ROUTE_MEMORY: UserMemoriesBackend(uid=context.uid),
            ROUTE_WORKSPACE: FilesystemBackend(
                root_dir=str(workspace_root),
                virtual_mode=True,
            ),
        },
    )


# 要记住一点：原生 FilesystemMiddleware 会把工具直接绑到 backend
class CustomFilesystemMiddleware(FilesystemMiddleware):

    async def awrap_tool_call(self, request, handler):
        tool_results = await handler(request)

        if self._tool_token_limit_before_evict is None:
            return tool_results

        if request.tool_call["name"] in EVICT_TOOL_EXEMPT:
            return tool_results

        return self._aintercept_large_tool_result(tool_results, request.runtime)

    def wrap_tool_call(self, request, handler):
        tool_results = handler(request)

        if self._tool_token_limit_before_evict is None:
            return tool_results

        if request.tool_call["name"] in EVICT_TOOL_EXEMPT:
            return tool_results

        return self._intercept_large_tool_result(tool_results, request.runtime)


def create_custom_filesystem_middleware(
    tool_token_limit_before_evict: int | None = None,
    *,
    context=None
) -> CustomFilesystemMiddleware:
    """创建绑定 CompositeBackend factory 的文件系统 middleware。"""
    return CustomFilesystemMiddleware(
        backend=create_composite_backend,
        tool_token_limit_before_evict=tool_token_limit_before_evict,
    )
