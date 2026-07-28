"""Agent 公共导出的按需加载入口。"""

from typing import Any

__all__ = [
    "BaseAgent",
    "BaseContext",
    "LeaderAgent",
    "agent_manager",
]


def __getattr__(name: str) -> Any:
    """按需加载 Agent，避免工具模块触发整套 Agent 注册。"""
    if name == "BaseAgent":
        from .base_agent import BaseAgent

        return BaseAgent
    if name == "BaseContext":
        from .base_context import BaseContext

        return BaseContext
    if name == "LeaderAgent":
        from .leaderagent import LeaderAgent

        return LeaderAgent
    if name == "agent_manager":
        from .manager import agent_manager

        return agent_manager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
