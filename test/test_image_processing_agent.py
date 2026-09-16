import unittest
from unittest.mock import AsyncMock, patch, sentinel

from src.agents.leaderagent.agent import LeaderAgent
from src.agents.leaderagent.context import LeaderAgentContext
from src.agents.manager import agent_manager
from src.agents.subagents.imageprocessingagent import ImageProcessingAgent
from src.agents.subagents.imageprocessingagent.context import ImageProcessingAgentContext


class ImageProcessingAgentTest(unittest.IsolatedAsyncioTestCase):
    async def test_selected_mcp_tools_are_attached_to_graph(self):
        module = "src.agents.subagents.imageprocessingagent.agent"
        context = ImageProcessingAgentContext(mcps=["image_server"], model="test/model")
        agent = ImageProcessingAgent()
        with (
            patch(f"{module}.get_mcp_tools", new_callable=AsyncMock) as get_tools,
            patch(f"{module}.list_mcp_servers", return_value=("image_server",)),
            patch(f"{module}.get_mcp_server_errors", return_value={}),
            patch(f"{module}.load_model", return_value=sentinel.model) as load_model,
            patch(f"{module}.create_agent", return_value=sentinel.graph) as create_agent,
            patch.object(agent, "get_checkpointer", return_value=sentinel.checkpointer),
            patch.object(agent, "get_store", return_value=sentinel.store),
        ):
            get_tools.return_value = (sentinel.image_tool,)
            result = await agent.get_agent(context)
        self.assertIs(result, sentinel.graph)
        get_tools.assert_awaited_once_with(["image_server"])
        load_model.assert_called_once_with("test/model")
        self.assertEqual(create_agent.call_args.kwargs["tools"], [sentinel.image_tool])
        self.assertIs(create_agent.call_args.kwargs["checkpointer"], sentinel.checkpointer)
        self.assertIs(create_agent.call_args.kwargs["store"], sentinel.store)

    def test_agent_is_internal_and_available_for_delegation(self):
        self.assertIsInstance(
            agent_manager.get_agent("ImageProcessingAgent"), ImageProcessingAgent
        )
        self.assertIn(
            "ImageProcessingAgent",
            {item["id"] for item in agent_manager.list_subagents()},
        )
        self.assertNotIn(
            "ImageProcessingAgent",
            {item["id"] for item in agent_manager.list_top_level_agents()},
        )
        middleware = LeaderAgent()._create_middlewares(LeaderAgentContext())[0]
        self.assertIn("image_processing_agent", middleware.subagent_slugs)


if __name__ == "__main__":
    unittest.main()
