"""动态工具分配覆盖目录校验、模型绑定和真实工具执行边界。"""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from deepagents.backends.protocol import ReadResult
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import Field

from src.agents import tool_catalog
from src.agents.backends.sandbox import CubeSandboxBackend
from src.agents.buildin.subagents import SubAgentContext, SubAgentGraph


class RecordingModel(FakeMessagesListChatModel):
    bound_tool_names: list[list[str]] = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        self.bound_tool_names.append([tool.name for tool in tools])
        return self

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def remote_tool(name):
    async def process(value: str = "input") -> str:
        return value

    return StructuredTool.from_function(name=name, description=f"处理图像：{name}", coroutine=process)


class DynamicAgentToolsTest(unittest.IsolatedAsyncioTestCase):
    async def invoke(self, context, responses):
        model = RecordingModel(responses=responses)
        agent = SubAgentGraph()
        with (
            patch("src.agents.buildin.subagents.subagent_graph.load_chat_model", AsyncMock(return_value=model)),
            patch.object(agent, "get_checkpointer", return_value=None),
            patch.object(agent, "get_store", return_value=None),
        ):
            graph = await agent.get_agent(context)
            result = await graph.ainvoke({"messages": [HumanMessage(content="执行子任务")]}, context=context)
        return graph, model, result

    async def test_empty_selection_has_no_tools_or_mcp_discovery(self):
        context = SubAgentContext(tools=[])
        with (
            patch.object(tool_catalog, "get_mcp_tools", AsyncMock()) as discover,
            patch("src.agents.middlewares.sandbox_middleware.get_sandbox_provider") as provider,
        ):
            self.assertEqual(await tool_catalog.resolve_spawn_tools(context, None), [])
            _, model, result = await self.invoke(context, [
                AIMessage(content="", tool_calls=[{"name": "execute", "args": {"command": "touch /forbidden"}, "id": "call-1"}]),
                AIMessage(content="完成分析"),
            ])
        discover.assert_not_awaited()
        provider.assert_not_called()
        self.assertEqual(model.bound_tool_names, [])
        response = next(message for message in result["messages"] if isinstance(message, ToolMessage))
        self.assertEqual(response.status, "error")
        self.assertIn("未分配工具：execute", response.content)
        self.assertEqual(result["messages"][-1].content, "完成分析")

    async def test_template_defaults_are_copied_and_explicit_selection_overrides_them(self):
        context = SubAgentContext(tools=["web_search", "knowledge_search"])
        with patch.object(tool_catalog, "get_mcp_tools", AsyncMock()) as discover:
            resolved = await tool_catalog.resolve_spawn_tools(context, None)
            self.assertEqual(resolved, context.tools)
            self.assertIsNot(resolved, context.tools)
            self.assertEqual(await tool_catalog.resolve_spawn_tools(context, ["read_file", "read_file"]), ["read_file"])
            self.assertEqual(await tool_catalog.resolve_spawn_tools(context, []), [])
        discover.assert_not_awaited()

    async def test_unknown_tool_is_rejected_before_loading_the_model(self):
        context = SubAgentContext(tools=["missing_tool"])
        with (
            patch.object(tool_catalog, "get_mcp_tools", AsyncMock(return_value=())),
            patch("src.agents.buildin.subagents.subagent_graph.load_chat_model", AsyncMock()) as model,
        ):
            with self.assertRaisesRegex(ValueError, "missing_tool"):
                await tool_catalog.resolve_spawn_tools(context, None)
            with self.assertRaisesRegex(ValueError, "missing_tool"):
                await SubAgentGraph().get_agent(context)
        model.assert_not_awaited()

    async def test_catalog_exposes_filesystem_local_and_current_mcp_tools(self):
        context = SubAgentContext(mcps=["imagery"])
        mcp = remote_tool("imagery_crop")
        with (
            patch.object(tool_catalog, "get_mcp_tools", AsyncMock(return_value=(mcp,))) as discover,
            patch.object(tool_catalog, "list_mcp_servers", return_value=("imagery",)),
            patch.object(tool_catalog, "get_mcp_server_errors", return_value={}),
        ):
            catalog = await tool_catalog.list_agent_tool_catalog(context)
        discover.assert_awaited_once_with(["imagery"])
        names = {entry["name"] for entry in catalog}
        self.assertTrue({"read_file", "execute", "web_search", "knowledge_search", "search_satellite_scenes", mcp.name} <= names)
        self.assertTrue(all(set(entry) == {"name", "description"} and entry["description"] for entry in catalog))
        self.assertTrue({"task", "subagent_start", "spawn_agent"}.isdisjoint(names))

    async def test_mcp_selection_does_not_grant_other_discovered_tools(self):
        context = SubAgentContext(tools=["imagery_crop"], mcps=["imagery"])
        with patch.object(tool_catalog, "get_mcp_tools", AsyncMock(return_value=(
            remote_tool("imagery_crop"), remote_tool("imagery_delete"),
        ))) as discover:
            self.assertEqual(await tool_catalog.resolve_spawn_tools(context, None), ["imagery_crop"])
            tools, mcp_names, filesystem = await tool_catalog.build_subagent_tools(context)
        self.assertEqual(discover.await_args.args, (["imagery"],))
        self.assertEqual([tool.name for tool in tools], ["imagery_crop"])
        self.assertEqual(mcp_names, {"imagery_crop"})
        self.assertIsNone(filesystem)

    async def test_legacy_unspecified_tools_materialize_existing_capabilities(self):
        context = SubAgentContext()
        with patch.object(tool_catalog, "get_mcp_tools", AsyncMock(return_value=(remote_tool("imagery_crop"),))):
            selected = await tool_catalog.resolve_spawn_tools(context, None)
        self.assertTrue({"web_search", "knowledge_search", "execute", "read_file", "imagery_crop"} <= set(selected))
        self.assertIsNone(context.tools)

    async def test_unassigned_filesystem_call_cannot_reach_the_sandbox(self):
        context = SubAgentContext(tools=["read_file"])
        with (
            patch.object(tool_catalog, "get_mcp_tools", AsyncMock()) as discover,
            patch("src.agents.middlewares.sandbox_middleware.get_sandbox_provider") as provider,
            patch.object(CubeSandboxBackend, "aexecute", AsyncMock()) as execute,
        ):
            _, model, result = await self.invoke(context, [
                AIMessage(content="", tool_calls=[{"name": "execute", "args": {"command": "touch /forbidden"}, "id": "call-1"}]),
                AIMessage(content="工具未分配"),
            ])
        discover.assert_not_awaited()
        provider.assert_not_called()
        execute.assert_not_awaited()
        self.assertTrue(model.bound_tool_names)
        self.assertTrue(all(names == ["read_file"] for names in model.bound_tool_names))
        response = next(message for message in result["messages"] if isinstance(message, ToolMessage))
        self.assertEqual(response.status, "error")
        self.assertIn("未分配工具：execute", response.content)

    async def test_assigned_filesystem_tool_executes_through_its_normal_middleware(self):
        context = SubAgentContext(tools=["read_file"], uid="user-1", thread_id="child-thread")
        provider = SimpleNamespace(acquire_async=AsyncMock(return_value="sandbox-1"), release=Mock())
        with (
            patch.object(tool_catalog, "get_mcp_tools", AsyncMock()) as discover,
            patch("src.agents.middlewares.sandbox_middleware.get_sandbox_provider", return_value=provider),
            patch.object(CubeSandboxBackend, "aread", AsyncMock(return_value=ReadResult(file_data={
                "content": "file evidence", "encoding": "utf-8", "created_at": "", "modified_at": "",
            }))) as read,
        ):
            _, model, result = await self.invoke(context, [
                AIMessage(content="", tool_calls=[{"name": "read_file", "args": {"file_path": "/workspace/input.txt"}, "id": "call-1"}]),
                AIMessage(content="读取完成"),
            ])
        discover.assert_not_awaited()
        read.assert_awaited_once()
        self.assertEqual(read.await_args.args, ("/workspace/input.txt",))
        provider.acquire_async.assert_awaited_once_with("user-1", "child-thread")
        provider.release.assert_called_once_with("sandbox-1")
        self.assertTrue(all(names == ["read_file"] for names in model.bound_tool_names))
        response = next(message for message in result["messages"] if isinstance(message, ToolMessage))
        self.assertEqual(response.status, "success")
        self.assertIn("file evidence", response.content)
