"""顶层编排角色。"""

from src.agents.agent_library import AgentLibrary
from src.configs import config

LEADER_AGENT = AgentLibrary(
    slug="LeaderAgent",
    name="leader_agent",
    description="通用多智能体编排器",
    backend_id="LeaderAgent",
    context={"model": config.default_model},
)
