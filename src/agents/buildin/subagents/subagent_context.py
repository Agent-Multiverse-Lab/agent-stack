from dataclasses import dataclass, field

from src.agents.base_context import BaseContext
from src.configs import config


@dataclass(kw_only=True)
class SubAgentContext(BaseContext):
    parent_thread_id: str | None = field(default=None)
    parent_run_id: str | None = field(default=None)
    gateway_target: str = field(default=config.satellite_gateway_target)
    gateway_project_id: str = field(default=config.satellite_gateway_project_id)
    gateway_timeout_seconds: float = field(default=config.satellite_gateway_timeout_seconds)
    require_mcp_tools: bool = field(default=False)
