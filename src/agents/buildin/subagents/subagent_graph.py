"""所有预定义子角色共用的执行图。"""

from langchain.agents import create_agent

from server.service.mcp_service import get_mcp_server_errors, get_mcp_tools, list_mcp_servers
from src.agents.backends.composite_backend import create_custom_filesystem_middleware
from src.agents.base_agent import BaseAgent
from src.agents.buildin.subagents.subagent_context import SubAgentContext
from src.agents.middlewares.image_validation_middleware import (
    ImageValidationMiddleware,
    create_image_validation_middleware,
)
from src.agents.middlewares.model_retry_middleware import create_model_retry_middleware
from src.agents.middlewares.sandbox_middleware import create_sandbox_middleware
from src.knowledge.tools import knowledge_search, web_search_one, web_search_parallel
from src.model import load_model
from src.third_party.satellite_gateway.tools import build_satellite_catalog_tools


async def _create_tools(context: SubAgentContext):
    mcp_tools = await get_mcp_tools(context.mcps)
    if context.require_mcp_tools or context.mcps:
        ImageValidationMiddleware.validate_mcp_tools(
            mcp_tools,
            context.mcps,
            list_mcp_servers(),
            get_mcp_server_errors(),
        )
    tools = [
        knowledge_search,
        web_search_parallel,
        web_search_one,
        *build_satellite_catalog_tools(context),
        *mcp_tools,
    ]
    return tools, {tool.name for tool in mcp_tools}


def _create_middlewares(context: SubAgentContext, *, mcp_tool_names: set[str]):
    return [
        create_sandbox_middleware(),
        create_custom_filesystem_middleware(context=context),
        create_image_validation_middleware(tool_names=mcp_tool_names),
        create_model_retry_middleware(),
    ]


class SubAgentGraph(BaseAgent):
    name: str = "创建子智能体"
    description: str = "创建子智能体的执行图，通过定义的subagentmiddlware的task工具"
    agent_context = SubAgentContext


    async def get_agent(self, context: SubAgentContext):
        """消费子 Run 自己的 Context，父 Run 只通过身份字段关联。"""
        tools, mcp_tool_names = await _create_tools(context)
        return create_agent(
            model=load_model(context.model),
            system_prompt=context.system_prompt,
            tools=tools,
            middleware=_create_middlewares(context, mcp_tool_names=mcp_tool_names),
            context_schema=SubAgentContext,
            checkpointer=self.get_checkpointer(),
            store=self.get_store(),
        )
