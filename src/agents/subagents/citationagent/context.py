from dataclasses import dataclass, field

from src.agents.base_context import BaseContext
from src.configs import config as sys_config


@dataclass(kw_only=True)
class CitationAgentContext(BaseContext):
    """CitationAgent 的运行配置。"""

    system_prompt: str = field(default="")
    model: str = field(default=sys_config.default_model)
