from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from deepagents.middleware.skills import SkillsMiddleware
from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelRetryMiddleware,
    TodoListMiddleware,
    ToolRetryMiddleware,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from server.service.mcp_service import get_mcp_tools
from server.service.model_service import load_chat_model
from src.agents.backends.composite_backend import (
    ROUTE_SKILL,
    create_composite_backend,
    create_custom_filesystem_middleware,
)
from src.agents.base_agent import BaseAgent
from src.agents.base_state import BaseState
from src.agents.buildin.leader.context import LeaderAgentContext
from src.agents.buildin.leader.present_artifacts import present_artifacts
from src.agents.buildin.leader.prompt import TODO_MIDDLEWARE_SYSTEM_PROMPT, build_prompt
from src.agents.buildin.leader.tools import ask_user, calculator
from src.agents.middlewares.memory_middleware import create_memory_middleware
from src.agents.middlewares.sandbox_middleware import create_sandbox_middleware
from src.agents.middlewares.subagent_middlware import create_subagent_middleware
from src.agents.middlewares.summary_middleware import (
    create_summary_middleware_from_context,
)


class LeaderAgent(BaseAgent):
    """负责规划、委派的顶层 Agent。"""

    name = "leader_agent"
    description = "通用多智能体编排器"
    context = LeaderAgentContext
    agent_context = LeaderAgentContext

    async def _create_middlewares(self, context, *, chat_model: BaseChatModel):
        backend = create_composite_backend(context)
        delegation = await create_subagent_middleware(parent_context=context)
        return [
            create_sandbox_middleware(),
            create_custom_filesystem_middleware(
                context=context,
                backend=backend,
            ),
            create_summary_middleware_from_context(
                context,
                backend=backend,
                model=chat_model,
            ),
            SkillsMiddleware(
                backend=backend,
                sources=[(ROUTE_SKILL, "Shared")],
            ),
            create_memory_middleware(),
            *([delegation] if delegation is not None else []),
            PatchToolCallsMiddleware(),
            ModelRetryMiddleware(max_retries=3, on_failure="continue"),
            ToolRetryMiddleware(max_retries=5),
            TodoListMiddleware(system_prompt=TODO_MIDDLEWARE_SYSTEM_PROMPT),
        ]

    async def get_agent(self, context=None) -> CompiledStateGraph:
        """消费已组装的 Context；不在构图过程中重新解析运行配置。"""
        runtime_context = context or self.context()
        mcp_tools = await get_mcp_tools(runtime_context.mcps)
        chat_model = await load_chat_model(runtime_context.model)
        # FIXEME: ask_user 仅注册到顶层 LeaderAgent，不扩散到 SubAgent。
        return await self._build_agent(
            runtime_context,
            tools=[*mcp_tools, ask_user, calculator, present_artifacts],
            chat_model=chat_model,
        )

    async def _build_agent(
        self,
        runtime_context: LeaderAgentContext,
        *,
        tools: list[BaseTool],
        chat_model: BaseChatModel,
    ) -> CompiledStateGraph:
        return create_agent(
            model=chat_model,
            tools=tools,
            system_prompt=build_prompt(runtime_context),
            state_schema=BaseState,
            context_schema=type(runtime_context),
            checkpointer=self.get_checkpointer(),
            store=self.get_store(),
            middleware=await self._create_middlewares(
                runtime_context,
                chat_model=chat_model,
            ),
        )  # ty:ignore[invalid-return-type]

