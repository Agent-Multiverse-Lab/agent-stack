from langchain.agents import create_agent
from langchain.agents.middleware import ModelRetryMiddleware
from langgraph.graph.state import CompiledStateGraph

from server.service.mcp_service import get_mcp_tools
from src.agents.base_agent import BaseAgent
from src.configs import config as sys_config
from src.model import load_model

from .context import SatelliteAgentContext
from .prompt import build_prompt
from .state import SatelliteAgentState


class SatelliteAgent(BaseAgent):
    """编排多源卫星数据检索与影像分析工具。"""

    name = "satellite_agent"
    description = (
        "Searches multiple satellite data sources and selects tools for catalog "
        "discovery, single-temporal interpretation, or multi-temporal change analysis."
    )
    context = SatelliteAgentContext
    agent_context = SatelliteAgentContext

    async def get_agent(self, context=None) -> CompiledStateGraph:
        runtime_context = context or self.context()
        tools = await get_mcp_tools(runtime_context.mcps)
        return create_agent(
            model=load_model(runtime_context.model or sys_config.default_model),
            tools=list(tools),
            system_prompt=build_prompt(runtime_context),
            state_schema=SatelliteAgentState,
            context_schema=type(runtime_context),
            checkpointer=self.get_checkpointer(),
            store=self.get_store(),
            middleware=[ModelRetryMiddleware(max_retries=1, on_failure="continue")],
        )  # ty:ignore[invalid-return-type]
