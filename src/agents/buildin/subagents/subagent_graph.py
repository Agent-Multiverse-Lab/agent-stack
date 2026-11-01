"""动态委派和预定义模板共用的子 Run 执行图。"""

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

from server.service.model_service import load_chat_model
from src.agents.base_agent import BaseAgent
from src.agents.buildin.subagents.subagent_context import SubAgentContext
from src.agents.middlewares.image_validation_middleware import create_image_validation_middleware
from src.agents.middlewares.model_retry_middleware import create_model_retry_middleware
from src.agents.middlewares.sandbox_middleware import create_sandbox_middleware
from src.agents.tool_catalog import build_subagent_tools


class AssignedToolsMiddleware(AgentMiddleware):
    """在沙箱等中间件产生副作用前拒绝未分配的工具调用。"""

    def __init__(self, tool_names: set[str]):
        super().__init__()
        self.tool_names = frozenset(tool_names)

    @staticmethod
    def _unassigned(request):
        return ToolMessage(
            content=f"本次子任务未分配工具：{request.tool_call['name']}",
            name=request.tool_call["name"],
            tool_call_id=request.tool_call["id"],
            status="error",
        )

    def wrap_tool_call(self, request, handler):
        if request.tool_call["name"] not in self.tool_names:
            return self._unassigned(request)
        return handler(request)

    async def awrap_tool_call(self, request, handler):
        if request.tool_call["name"] not in self.tool_names:
            return self._unassigned(request)
        return await handler(request)


class SubAgentGraph(BaseAgent):
    name: str = "子任务执行器"
    description: str = "使用分配的工具和上下文执行独立子 Run"
    agent_context = SubAgentContext

    async def get_agent(self, context: SubAgentContext):
        """消费子 Run 自己的 Context，父 Run 只通过身份字段关联。"""
        tools, mcp_tool_names, filesystem = await build_subagent_tools(context)
        tool_names = {tool.name for tool in tools}
        if filesystem:
            tool_names.update(tool.name for tool in filesystem.tools)
        middleware = [AssignedToolsMiddleware(tool_names)]
        if filesystem:
            middleware.extend([create_sandbox_middleware(), filesystem])
        middleware.extend([
            create_image_validation_middleware(tool_names=mcp_tool_names),
            create_model_retry_middleware(),
        ])
        chat_model = await load_chat_model(context.model)
        return create_agent(
            model=chat_model,
            system_prompt=context.system_prompt,
            tools=tools,
            middleware=middleware,
            context_schema=SubAgentContext,
            checkpointer=self.get_checkpointer(),
            store=self.get_store(),
        )
