from __future__ import annotations

from typing import Annotated, Literal, NotRequired, TypedDict

from langchain.agents import AgentState


def merge_artifacts(existing: list[str] | None, new: list[str] | None) -> list[str]:
    """对交付物路径保序去重。"""
    return list(dict.fromkeys((existing or []) + (new or [])))


class BaseState(AgentState):
    # 由 present_artifacts 工具登记、前端展示的 /workspace 交付物路径。
    artifacts: NotRequired[Annotated[list[str], merge_artifacts]]


class AgentTodoDTO(TypedDict):
    """传给前端的待办项。"""

    content: str
    status: Literal["pending", "in_progress", "completed"]


class SubagentRunDTO(TypedDict):
    """传给前端的子 Agent 运行摘要。"""

    run_id: str
    agent_slug: str
    status: str


class AgentStateDTO(TypedDict):
    """Service 层输出的 Agent 状态传输对象。"""

    agent_todo: list[AgentTodoDTO]
    subagent_runs: NotRequired[list[SubagentRunDTO]]
