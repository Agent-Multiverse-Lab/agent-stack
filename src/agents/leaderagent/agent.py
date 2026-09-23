from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from deepagents.middleware.skills import SkillsMiddleware
from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelRetryMiddleware,
    TodoListMiddleware,
    ToolRetryMiddleware,
)
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from server.service.mcp_service import get_mcp_tools
from src.agents.backends.composite_backend import (
    ROUTE_SKILL,
    create_composite_backend,
    create_custom_filesystem_middleware,
)
from src.agents.base_agent import BaseAgent
from src.agents.middlewares.memory_middleware import create_memory_middleware
from src.agents.middlewares.sandbox_middleware import create_sandbox_middleware
from src.agents.middlewares.subagent_middlware import create_subagent_middleware
from src.agents.middlewares.summary_middleware import (
    create_summary_middleware_from_context,
)
from src.agents.subagents.citationagent import CitationAgent
from src.agents.subagents.imageprocessingagent import ImageProcessingAgent
from src.agents.subagents.satelliteagent import SatelliteAgent
from src.agents.subagents.searchagent import SearchAgent
from src.configs import config as sys_config
from src.model import load_model

from .context import LeaderAgentContext
from .prompt import TODO_MIDDLEWARE_SYSTEM_PROMPT, build_prompt
from .tools import ask_user, calculator


class LeaderAgent(BaseAgent):
    """负责规划、委派的顶层 Agent。"""

    name = "leader_agent"
    description = "通用多智能体编排器"
    context = LeaderAgentContext
    agent_context = LeaderAgentContext

    def __init__(self):
        pass

    def _create_middlewares(self, context):
        backend = create_composite_backend(context)
        return [
            create_sandbox_middleware(),
            create_custom_filesystem_middleware(
                context=context,
                backend=backend,
            ),
            create_summary_middleware_from_context(
                context,
                backend=backend,
            ),
            SkillsMiddleware(
                backend=backend,
                sources=[(ROUTE_SKILL, "Shared")],
            ),
            create_memory_middleware(),
            create_subagent_middleware(
                subagents=[
                    SearchAgent(),
                    CitationAgent(),
                    ImageProcessingAgent(),
                    SatelliteAgent(),
                ],
                parent_context=context,
            ),
            PatchToolCallsMiddleware(),
            ModelRetryMiddleware(max_retries=3, on_failure="continue"),
            ToolRetryMiddleware(max_retries=5),
            TodoListMiddleware(system_prompt=TODO_MIDDLEWARE_SYSTEM_PROMPT),
        ]

    async def get_agent(self, context=None) -> CompiledStateGraph:
        runtime_context = context or self.context()
        mcp_tools = await get_mcp_tools(runtime_context.mcps)
        # FIXEME: ask_user 仅注册到顶层 LeaderAgent，不扩散到 SubAgent。
        return self._build_agent(
            runtime_context,
            tools=[*mcp_tools, ask_user, calculator],
        )

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
            store=self.get_store(),
            middleware=self._create_middlewares(runtime_context),
        )  # ty:ignore[invalid-return-type]
