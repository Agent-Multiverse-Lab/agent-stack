from langchain.agents import create_agent
from langchain.agents.middleware import ModelRetryMiddleware
from langgraph.graph.state import CompiledStateGraph

from server.service.mcp_service import get_mcp_server_errors, get_mcp_tools, list_mcp_servers
from src.agents.base_agent import BaseAgent
from src.configs import config as sys_config
from src.model import load_model

from .context import ImageProcessingAgentContext
from .middlewares import ImageValidationMiddleware
from .prompt import build_prompt
from .state import ImageProcessingAgentState


class ImageProcessingAgent(BaseAgent):
    """通过 MCP 工具执行图像处理并返回产物引用。"""

    name = "image_processing_agent"
    description = (
        "Processes existing images with MCP tools: crop, resize, convert, enhance, "
        "detect, segment, or compare images, depending on available tools. "
        "Provide tool-accessible image URLs, paths or asset IDs and processing parameters."
    )
    context = ImageProcessingAgentContext
    agent_context = ImageProcessingAgentContext

    async def get_agent(self, context=None) -> CompiledStateGraph:
        runtime_context = context or self.context()
        tools = await get_mcp_tools(runtime_context.mcps)
        ImageValidationMiddleware.validate_mcp_tools(
            tools, [name.strip() for name in runtime_context.mcps if name.strip()],
            list_mcp_servers(), get_mcp_server_errors(),
        )
        return create_agent(
            model=load_model(runtime_context.model or sys_config.default_model),
            tools=list(tools),
            system_prompt=build_prompt(runtime_context),
            state_schema=ImageProcessingAgentState,
            context_schema=type(runtime_context),
            checkpointer=self.get_checkpointer(),
            store=self.get_store(),
            middleware=[
                ImageValidationMiddleware(),
                ModelRetryMiddleware(max_retries=1, on_failure="continue"),
            ],
        )
