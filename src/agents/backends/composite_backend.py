"""
基于 deepagents 后端和文件系统构建通往沙箱的路径。

CompositeBackend 按虚拟路径前缀路由，各后端路径直接来自运行时上下文。
"""
from __future__ import annotations

from pathlib import Path

from deepagents.backends import BackendProtocol, CompositeBackend, FilesystemBackend
from deepagents.middleware.filesystem import FilesystemMiddleware

from src.agents.backends.memories_backend import UserMemoriesBackend
from src.agents.backends.sandbox import S2CSandbox
from src.agents.base_context import BaseContext
from src.configs.config import config as sys_config

EVICT_TOOL_EXEMPT = {"read_file"}  # 直接返回 read_file 的长结果，避免写入部分后端

# 智能体可见的虚拟路径前缀（组合路由的键，建议以 / 结尾）
ROUTE_SKILL = "/skill/"
ROUTE_MEMORY = "/memory/"
ROUTE_WORKSPACE = "/workspace/"


def create_composite_backend(context: BaseContext) -> CompositeBackend:
    """为单次 Agent 运行构建隔离的 CompositeBackend。"""
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
        artifacts_root=f"{ROUTE_WORKSPACE.rstrip('/')}/outputs",
    )


# 原生 FilesystemMiddleware 会将工具直接绑定到后端。
class CustomFilesystemMiddleware(FilesystemMiddleware):

    async def awrap_tool_call(self, request, handler):
        tool_results = await handler(request)

        if self._tool_token_limit_before_evict is None:
            return tool_results

        if request.tool_call["name"] in EVICT_TOOL_EXEMPT:
            return tool_results

        return await self._aintercept_large_tool_result(tool_results, request.runtime)

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
    context: BaseContext,
    backend: BackendProtocol | None = None,
) -> CustomFilesystemMiddleware:
    """为本次 Agent 运行构建按需连接的 Sandbox 文件系统中间件。"""
    return CustomFilesystemMiddleware(
        backend=backend or S2CSandbox(thread_id=context.thread_id, uid=context.uid),
        tool_token_limit_before_evict=tool_token_limit_before_evict,
    )
