from __future__ import annotations

from typing import Annotated, NotRequired, TypedDict

from langchain.agents import AgentState


def merge_artifacts(existing: list[str] | None, new: list[str] | None) -> list[str]:
    """对交付物路径保序去重。"""
    return list(dict.fromkeys((existing or []) + (new or [])))


class BaseState(AgentState):
    # 由 present_artifacts 工具登记、前端展示的 /workspace 交付物路径。
    artifacts: NotRequired[Annotated[list[str], merge_artifacts]]


class CustomAgentState(TypedDict):
    todos: list # todo middlware的开放字段，用于前端传输
