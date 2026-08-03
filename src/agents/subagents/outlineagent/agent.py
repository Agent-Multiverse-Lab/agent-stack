from langchain.agents import create_agent
from langchain.agents.middleware import ModelRetryMiddleware
from langgraph.graph.state import CompiledStateGraph

from src.agents.base_agent import BaseAgent
from src.model import load_model
from src.configs import config as sys_config

from .context import OutlineAgentContext


class OutlineAgent(BaseAgent):
    name = "outline_agent"
    description = "Designs the story structure and produces an outline artifact."
    context = OutlineAgentContext
    agent_context = OutlineAgentContext
    required_artifacts: tuple[str, ...] = ()
    output_artifact = "outline"

    async def get_agent(self, context=None) -> CompiledStateGraph:
        runtime_context = context or self.context()
        return create_agent(
            model=load_model(runtime_context.model or sys_config.default_model),
            tools=[],
            system_prompt=runtime_context.system_prompt,
            context_schema=type(runtime_context),
            checkpointer=self.get_checkpointer(),
            store=self.get_store(),
            middleware=[ModelRetryMiddleware(max_retries=1, on_failure="continue")],  # ty:ignore[invalid-argument-type]
        )  # ty:ignore[invalid-return-type]
