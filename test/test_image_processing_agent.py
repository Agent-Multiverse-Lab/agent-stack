import unittest
from unittest.mock import AsyncMock, patch, sentinel

from src.agents.agent_library.subagents.image_processing import IMAGE_AGENT
from src.agents.buildin.subagents import SubAgentContext, SubAgentGraph


class ImageProcessingAgentTest(unittest.IsolatedAsyncioTestCase):
    async def test_selected_mcp_tools_are_attached_to_common_graph(self):
        module = "src.agents.buildin.subagents.subagent_graph"
        context = SubAgentContext(uid="user-1", thread_id="thread-1")
        context.update_context(IMAGE_AGENT.context)
        context.update_context({"mcps": ["image_server"], "model": "test/model"})
        agent = SubAgentGraph()
        with (
            patch(f"{module}.get_mcp_tools", AsyncMock(return_value=(sentinel.image_tool,))) as get_tools,
            patch(f"{module}.list_mcp_servers", return_value=("image_server",)),
            patch(f"{module}.get_mcp_server_errors", return_value={}),
            patch(f"{module}.load_model", return_value=sentinel.model) as load_model,
            patch(f"{module}.create_agent", return_value=sentinel.graph) as create_agent,
            patch.object(agent, "get_checkpointer", return_value=sentinel.checkpointer),
            patch.object(agent, "get_store", return_value=sentinel.store),
        ):
            result = await agent.get_agent(context)
        self.assertIs(result, sentinel.graph)
        get_tools.assert_awaited_once_with(["image_server"])
        load_model.assert_called_once_with("test/model")
        self.assertIn(sentinel.image_tool, create_agent.call_args.kwargs["tools"])
        self.assertIs(create_agent.call_args.kwargs["checkpointer"], sentinel.checkpointer)
        self.assertIs(create_agent.call_args.kwargs["store"], sentinel.store)

    async def test_image_role_still_requires_available_mcp_tools(self):
        context = SubAgentContext(uid="user-1", thread_id="thread-1")
        context.update_context(IMAGE_AGENT.context)
        with patch("src.agents.buildin.subagents.subagent_graph.get_mcp_tools", AsyncMock(return_value=[])):
            with self.assertRaisesRegex(ValueError, "没有可用的 MCP 工具"):
                await SubAgentGraph().get_agent(context)
