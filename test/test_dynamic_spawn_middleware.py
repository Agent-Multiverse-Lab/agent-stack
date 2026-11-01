"""动态委派工具的模型输入、运行身份和提问互斥。"""

import json
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage

from src.agents.base_context import BaseContext
from src.agents.middlewares.subagent_middlware import SubAgentMiddleware, create_subagent_middleware


@asynccontextmanager
async def fake_session():
    yield object()


class DynamicSpawnMiddlewareTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.parent = BaseContext(uid="user-1", thread_id="parent-thread", run_id="parent-run", request_id="req-1")
        self.middleware = SubAgentMiddleware(subagents=[], parent_context=self.parent)
        self.tools = {tool.name: tool for tool in self.middleware.tools}
        self.runtime = SimpleNamespace(tool_call_id="call-spawn", state={"messages": []})
        self.record = {"run_id": "child-run", "thread_id": "child-thread", "status": "pending"}
        self.service = SimpleNamespace(create_spawn_record=AsyncMock(return_value=self.record))

    async def test_spawn_without_template_passes_explicit_task_context_and_returns_run(self):
        with (
            patch("src.agents.middlewares.subagent_middlware.session_context", fake_session),
            patch("src.agents.middlewares.subagent_middlware._subagent_run_service", return_value=self.service),
        ):
            result = await self.tools["spawn_agent"].coroutine(
                task="比较两份资料", tools=[], context="只使用提供的材料", runtime=self.runtime,
            )
        message = result.update["messages"][0]
        self.assertEqual(json.loads(message.content), self.record)
        self.assertEqual(message.status, "success")
        self.assertEqual(message.additional_kwargs["subagent_run_id"], "child-run")
        self.service.create_spawn_record.assert_awaited_once_with(
            created_by_run_id="parent-run", uid="user-1", request_id="req-1", tool_call_id="call-spawn",
            task="比较两份资料", tools=[], context="只使用提供的材料", template=None,
        )

    async def test_factory_keeps_dynamic_delegation_when_template_directory_is_empty(self):
        repository = SimpleNamespace(list_agents=AsyncMock(return_value=[]))
        with (
            patch("src.agents.middlewares.subagent_middlware.session_context", fake_session),
            patch("src.agents.middlewares.subagent_middlware.AgentRepository", return_value=repository),
        ):
            middleware = await create_subagent_middleware(parent_context=self.parent)
        names = {tool.name for tool in middleware.tools}
        self.assertTrue({"spawn_agent", "list_agent_tools", "subagent_status", "subagent_await", "subagent_cancel"} <= names)
        self.assertIn("spawn_agent", middleware._system_prompt())

    def test_schema_exposes_task_configuration_without_runtime_identity(self):
        schema = self.tools["spawn_agent"].args_schema.model_json_schema()
        self.assertEqual(schema["required"], ["task"])
        self.assertEqual(set(schema["properties"]), {"task", "tools", "context", "template"})

    async def test_unknown_template_is_reported_without_creating_run(self):
        with patch("src.agents.middlewares.subagent_middlware.session_context") as session:
            result = await self.tools["spawn_agent"].coroutine(
                task="查询资料", template="missing-template", runtime=self.runtime,
            )
        self.assertEqual(result.update["messages"][0].status, "error")
        self.assertIn("missing-template", result.update["messages"][0].content)
        session.assert_not_called()

    async def test_same_round_question_blocks_spawn_before_persistence(self):
        self.runtime.state["messages"] = [AIMessage(content="", tool_calls=[
            {"id": "call-spawn", "name": "spawn_agent", "args": {"task": "检索"}},
            {"id": "call-question", "name": "ask_user", "args": {"questions": []}},
        ])]
        with patch("src.agents.middlewares.subagent_middlware.session_context") as session:
            result = await self.tools["spawn_agent"].coroutine(task="检索", runtime=self.runtime)
        self.assertEqual(result.update["messages"][0].status, "error")
        self.assertIn("ask_user", result.update["messages"][0].content)
        session.assert_not_called()

    async def test_previous_question_does_not_block_a_new_spawn_call(self):
        self.runtime.state["messages"] = [
            AIMessage(content="", tool_calls=[{"id": "old-question", "name": "ask_user", "args": {}}]),
            AIMessage(content="", tool_calls=[{"id": "call-spawn", "name": "spawn_agent", "args": {"task": "检索"}}]),
        ]
        with (
            patch("src.agents.middlewares.subagent_middlware.session_context", fake_session),
            patch("src.agents.middlewares.subagent_middlware._subagent_run_service", return_value=self.service),
        ):
            result = await self.tools["spawn_agent"].coroutine(task="检索", runtime=self.runtime)
        self.assertEqual(result.update["messages"][0].additional_kwargs["subagent_run_id"], "child-run")

    async def test_catalog_returns_available_names_and_descriptions(self):
        entries = [{"name": "web_search", "description": "网页搜索"}]
        self.parent.mcps = ["parent-only-server"]
        with patch("src.agents.tool_catalog.list_agent_tool_catalog", AsyncMock(return_value=entries)) as catalog:
            result = await self.tools["list_agent_tools"].coroutine()
        self.assertEqual(json.loads(result), entries)
        self.assertEqual(catalog.call_args.args[0].mcps, [])

    async def test_invalid_tool_selection_returns_error_without_a_run_identifier(self):
        self.service.create_spawn_record.side_effect = ValueError("未知工具：missing-tool")
        with (
            patch("src.agents.middlewares.subagent_middlware.session_context", fake_session),
            patch("src.agents.middlewares.subagent_middlware._subagent_run_service", return_value=self.service),
        ):
            result = await self.tools["spawn_agent"].coroutine(task="检索", tools=["missing-tool"], runtime=self.runtime)
        message = result.update["messages"][0]
        self.assertEqual(message.status, "error")
        self.assertIsNone(message.additional_kwargs["subagent_run_id"])
        self.assertIn("missing-tool", message.content)


if __name__ == "__main__":
    unittest.main()
