from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from langchain.agents import create_agent
from langchain.agents.middleware import ModelRetryMiddleware, TodoListMiddleware
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from server.service.mcp_service import get_mcp_tools
from src.agents.backends.composite_backend import (
    create_custom_filesystem_middleware,
)
from src.agents.base_agent import BaseAgent
from src.agents.middlewares.subagent_middlware import create_subagent_middleware
from src.agents.subagents.outlineagent import OutlineAgent
from src.agents.subagents.searchagent import SearchAgent
from src.model import load_model
from src.configs import config as sys_config

from .context import LeaderAgentContext
from .prompt import build_prompt


class LeaderAgent(BaseAgent):
    """负责规划、委派并整合剧本与分镜创作任务的公开顶层 Agent。"""

    name = "leader_agent"
    description = "创作负责人"
    context = LeaderAgentContext
    agent_context = LeaderAgentContext

    def __init__(self):
        pass

    def _create_middlewares(self, context):
        return [
            create_custom_filesystem_middleware(context=context),
            create_subagent_middleware(
                subagents=[
                    SearchAgent(),
                    OutlineAgent(),
                ],
                parent_context=context,
            ),
            PatchToolCallsMiddleware(),
            ModelRetryMiddleware(max_retries=1, on_failure="continue"),
            TodoListMiddleware(),
        ]

    async def get_agent(self, context=None) -> CompiledStateGraph:
        runtime_context = context or self.context()
        mcp_tools = await get_mcp_tools(runtime_context.mcps)
        return self._build_agent(runtime_context, tools=list(mcp_tools))

    def _build_agent(
        self,
        runtime_context: LeaderAgentContext,
        *,
        tools: list[BaseTool],
    ) -> CompiledStateGraph:
        return create_agent(
            model=load_model(runtime_context.model or sys_config.default_model),
            tools=tools,
            system_prompt=build_prompt(runtime_context),
            context_schema=type(runtime_context),
            checkpointer=self.get_checkpointer(),
            middleware=self._create_middlewares(runtime_context),
        )  # ty:ignore[invalid-return-type]
