"""Agent 属性模型及启动时用于补齐数据库记录的角色预设。"""

import json
from copy import deepcopy
from dataclasses import dataclass, fields
from importlib import import_module
from pkgutil import walk_packages
from typing import Any

from src.agents.base_context import BaseContext


@dataclass(kw_only=True, frozen=True)
class AgentLibrary:
    slug: str
    name: str
    description: str
    backend_id: str
    context: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.slug.strip() or not self.name.strip():
            raise ValueError("Agent slug 和名称不能为空")
        if self.backend_id not in {"LeaderAgent", "SubAgentGraph"}:
            raise ValueError(f"未知 Agent backend：{self.backend_id}")
        if not isinstance(self.context, dict):
            raise ValueError("Agent Context 配置必须是字典")
        if {"uid", "run_id", "thread_id", "request_id", "parent_run_id", "parent_thread_id"} & self.context.keys():
            raise ValueError("Agent 预设配置不能包含 Run 身份")
        json.dumps(self.context, allow_nan=False)
        object.__setattr__(self, "context", deepcopy(self.context))

    def validate_context(self, context_class: type[BaseContext]) -> None:
        unknown_fields = self.context.keys() - {item.name for item in fields(context_class)}
        if unknown_fields:
            raise ValueError(f"未知 Agent Context 参数：{', '.join(sorted(unknown_fields))}")


def discover_agents() -> dict[str, AgentLibrary]:
    """递归收集 library 中的 AgentLibrary 实例，重复导出合并，同 slug 的不同实例报错。"""
    agents: dict[str, AgentLibrary] = {}
    sources: dict[str, str] = {}
    for module_info in walk_packages(__path__, prefix=f"{__name__}."):
        module = import_module(module_info.name)
        for value in vars(module).values():
            if not isinstance(value, AgentLibrary):
                continue
            existing = agents.get(value.slug)
            if existing is not None and existing is not value:
                raise ValueError(f"Agent slug 重复：{value.slug}（{sources[value.slug]}、{module.__name__}）")
            agents[value.slug] = value
            sources.setdefault(value.slug, module.__name__)
    return agents
