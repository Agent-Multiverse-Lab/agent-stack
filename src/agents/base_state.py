from __future__ import annotations

from typing import TypedDict

from langchain.agents import AgentState


class BaseState(AgentState):
    pass


class CustomAgentState(TypedDict):
    todos: list # todo middlware的开放字段，用于前端传输
    