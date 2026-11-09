from dataclasses import dataclass, field

from src.agents.base_context import BaseContext


@dataclass(kw_only=True)
class SubAgentContext(BaseContext):
    parent_thread_id: str | None = field(default=None)
    created_by_run_id: str | None = field(default=None)
    require_mcp_tools: bool = field(default=False)
