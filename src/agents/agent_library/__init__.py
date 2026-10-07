"""预定义 Agent 的角色配置实体。"""

import json
from copy import deepcopy
from dataclasses import dataclass, fields
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

    @classmethod
    def from_record(cls, record: Any) -> "AgentLibrary":
        return cls(
            slug=record.slug,
            name=record.name,
            description=record.description,
            backend_id=record.backend_id,
            context=record.agent_config or {},
        )
