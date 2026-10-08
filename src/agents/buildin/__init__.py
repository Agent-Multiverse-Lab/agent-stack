"""内置 Agent 的执行实现。"""

from src.agents.base_agent import BaseAgent
from src.agents.buildin.leader.agent import LeaderAgent
from src.agents.buildin.subagents.subagent_graph import SubAgentGraph

AGENT_CLASSES: dict[str, type[BaseAgent]] = {
    "LeaderAgent": LeaderAgent,
    "SubAgentGraph": SubAgentGraph,
}


def get_agent_class(backend_id: str) -> type[BaseAgent]:
    agent_class = AGENT_CLASSES.get(backend_id)
    if agent_class is None:
        raise ValueError(f"未知 Agent backend：{backend_id}")
    return agent_class
