"""Agent 公共导出的按需加载入口。"""

from typing import Any

__all__ = [
    "BaseAgent",
    "BaseContext",
    "LeaderAgent",
    "CustomAgentState"
]


def __getattr__(name: str) -> Any:
    """按需加载 Agent，避免工具模块触发整套 Agent 注册。"""
    if name == "BaseAgent":
        from src.agents.base_agent import BaseAgent

        return BaseAgent
    if name == "BaseContext":
        from src.agents.base_context import BaseContext

        return BaseContext
    if name == "LeaderAgent":
        from src.agents.buildin.leader.agent import LeaderAgent

        return LeaderAgent
    if name == "CustomAgentState":
            from src.agents.base_state import CustomAgentState
    
            return CustomAgentState
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
