from langchain.agents import create_agent
from langchain.agents.middleware import ModelRetryMiddleware
from langgraph.graph.state import CompiledStateGraph

from src.agents.base_agent import BaseAgent
from src.configs import config as sys_config
from src.model import load_model

from .context import CitationAgentContext
from .prompt import build_prompt
from .state import CitationAgentState


class CitationAgent(BaseAgent):
    """验证回答声明与检索证据之间的引用关系。"""

    name = "citation_agent"
    description = "Validates whether cited retrieval evidence supports each claim."
    context = CitationAgentContext
    agent_context = CitationAgentContext

    async def get_agent(self, context=None) -> CompiledStateGraph:
        """构造当前运行使用的 CitationAgent Graph。"""

        runtime_context = context or self.context()
        return create_agent(
            model=load_model(
                runtime_context.model or sys_config.default_model
            ),
            tools=[],
            system_prompt=build_prompt(runtime_context),
            state_schema=CitationAgentState,
            context_schema=type(runtime_context),
            checkpointer=self.get_checkpointer(),
            store=self.get_store(),
            middleware=[
                ModelRetryMiddleware(max_retries=1, on_failure="continue"),
            ],
        )  # ty:ignore[invalid-return-type]
