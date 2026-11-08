"""资料检索角色的预定义配置。"""

from src.agents.library import AgentLibrary
from src.agents.library.subagents.prompts.search.v6 import SYSTEM_PROMPT
from src.configs import config

SEARCH_AGENT = AgentLibrary(
    slug="search_agent",
    name="资料检索",
    description="检索资料、比较来源并整理证据",
    backend_id="SubAgentGraph",
    context={"system_prompt": SYSTEM_PROMPT, "model": config.flash_model},
)
