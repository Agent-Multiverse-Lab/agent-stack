"""显式导出各角色实体，供 Worker 同步注册。"""

from .citation import CITATION_AGENT
from .image_processing import IMAGE_AGENT
from .satellite import SATELLITE_AGENT
from .search import SEARCH_AGENT

SUBAGENTS = (SEARCH_AGENT, CITATION_AGENT, IMAGE_AGENT, SATELLITE_AGENT)
