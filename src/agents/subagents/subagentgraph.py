"""所有预定义子角色共用的执行图。"""

from typing import Any, NotRequired

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import ModelRetryMiddleware

from server.service.mcp_service import get_mcp_server_errors, get_mcp_tools, list_mcp_servers
from src.agents.agent_library import AgentLibrary
from src.agents.backends.composite_backend import create_custom_filesystem_middleware
from src.agents.base_agent import BaseAgent
from src.agents.middlewares.image_validation_middleware import ImageValidationMiddleware
from src.agents.middlewares.sandbox_middleware import create_sandbox_middleware
from src.configs import config
from src.knowledge.tools import knowledge_search, web_search_one, web_search_parallel
from src.model import load_model
from src.third_party.satellite_gateway.tools import build_satellite_catalog_tools

from .subagent_context import SubAgentContext


class SubAgentState(AgentState):
    """保留检索、校验和卫星任务的可选状态字段。"""

    draft: NotRequired[str]
    claims: NotRequired[list[dict[str, Any]]]
    sources: NotRequired[list[dict[str, Any]]]
    task_type: NotRequired[str]
    asset_ids: NotRequired[list[str]]
    area_of_interest: NotRequired[str]
    time_range: NotRequired[str]


class SubAgentGraph(BaseAgent):
    agent_context = SubAgentContext

    def __init__(self, *, definition: AgentLibrary):
        super().__init__()
        self.definition = definition
        self.name = definition.name
        self.description = definition.description
        self._mcp_tool_names: set[str] = set()

    async def _create_tools(self, context: SubAgentContext):
        mcp_tools = await get_mcp_tools(context.mcps)
        if context.require_mcp_tools or context.mcps:
            ImageValidationMiddleware.validate_mcp_tools(
                mcp_tools,
                context.mcps,
                list_mcp_servers(),
                get_mcp_server_errors(),
            )
        self._mcp_tool_names = {tool.name for tool in mcp_tools}
        return [
            knowledge_search,
            web_search_parallel,
            web_search_one,
            *build_satellite_catalog_tools(context),
            *mcp_tools,
        ]

    def _create_middlewares(self, context: SubAgentContext):
        return [
            create_sandbox_middleware(),
            create_custom_filesystem_middleware(context=context),
            ImageValidationMiddleware(tool_names=self._mcp_tool_names),
            ModelRetryMiddleware(max_retries=1, on_failure="continue"),
        ]

    async def get_agent(self, context: SubAgentContext):
        tools = await self._create_tools(context)
        return create_agent(
            model=load_model(context.model or config.default_model),
            system_prompt=context.system_prompt,
            tools=tools,
            middleware=self._create_middlewares(context),
            state_schema=SubAgentState,
            context_schema=SubAgentContext,
            checkpointer=self.get_checkpointer(),
            store=self.get_store(),
        )
