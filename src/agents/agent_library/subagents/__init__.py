"""显式导出各角色实体，供 Worker 同步注册。"""

from src.agents.agent_library.subagents.citation import CITATION_AGENT
from src.agents.agent_library.subagents.image_processing import IMAGE_AGENT
from src.agents.agent_library.subagents.satellite import SATELLITE_AGENT
from src.agents.agent_library.subagents.search import SEARCH_AGENT

SUBAGENTS = (SEARCH_AGENT, CITATION_AGENT, IMAGE_AGENT, SATELLITE_AGENT)
