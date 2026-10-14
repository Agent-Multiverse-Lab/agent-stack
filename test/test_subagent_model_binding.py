"""子会话绑定子角色模型，Run 保存同一模型快照。"""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from server.service import subagent_service


class SubAgentModelBindingTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = SimpleNamespace(flush=AsyncMock(), commit=AsyncMock(), rollback=AsyncMock())
        self.agent = SimpleNamespace(agent_config={"model": "deepseek/deepseek-v4-flash"})
        self.agents = SimpleNamespace(get_by_slug_for_run_type=AsyncMock(return_value=self.agent))
        self.parent = SimpleNamespace(id="parent-run", uid="user-1", conversation_id=1,
                                      run_metadata={"model": "dashscope/qwen3.8-max"})
        self.runs = SimpleNamespace(get_by_id=AsyncMock(return_value=self.parent), create_run=AsyncMock())
        self.conversations = SimpleNamespace(
            get_conversation_by_id=AsyncMock(return_value=SimpleNamespace(id=1, uid="user-1")),
            create_conversation=AsyncMock(), create_agent_input_message=AsyncMock(),
        )

        async def conversation(**values):
            return SimpleNamespace(id=2, agent_id=values["agent_slug"], **{key: value for key, value in values.items() if key != "agent_slug"})

        async def message(**values):
            return SimpleNamespace(id=3, role="user", status="pending", request_id=None, agent_run_id=None, **values)

        async def run(**values):
            return SimpleNamespace(id=values["run_id"], agent_id=values["agent_slug"], agent_status="pending", **{
                key: value for key, value in values.items() if key not in {"run_id", "agent_slug"}
            })

        self.conversations.create_conversation.side_effect = conversation
        self.conversations.create_agent_input_message.side_effect = message
        self.runs.create_run.side_effect = run
        self.enqueue = AsyncMock()
        for target, value in (
            ("AgentRepository", self.agents), ("AgentRunRepository", self.runs),
            ("ConversationRepository", self.conversations),
        ):
            current = patch.object(subagent_service, target, return_value=value)
            current.start()
            self.addCleanup(current.stop)
        current = patch.object(subagent_service.agent_run_service, "enqueue_agent_run", self.enqueue)
        current.start()
        self.addCleanup(current.stop)

    async def create(self):
        return await subagent_service.SubAgentRunService(self.db).create_subagent_record(
            parent_run_id="parent-run", agent_slug="search_agent", uid="user-1", tool_call_id="tool-1", request_id="request-1",
            input_message=SimpleNamespace(content="Search", image_content=None, msg_type="text"),
        )

    async def test_child_binds_its_own_agent_model_and_run_snapshot(self):
        record = await self.create()
        self.agents.get_by_slug_for_run_type.assert_awaited_once_with(slug="search_agent", run_type="subagent")
        self.assertEqual(self.conversations.create_conversation.await_args.kwargs["conversation_metadata"],
                         {"model": "deepseek/deepseek-v4-flash"})
        self.assertEqual(self.runs.create_run.await_args.kwargs["run_metadata"],
                         {"model": "deepseek/deepseek-v4-flash", "tool_call_id": "tool-1"})
        self.db.commit.assert_awaited_once()
        self.enqueue.assert_awaited_once_with(record["run_id"])

    async def test_missing_agent_model_falls_back_to_config(self):
        self.agent.agent_config = {}
        await self.create()
        self.assertEqual(self.runs.create_run.await_args.kwargs["run_metadata"]["model"], "dashscope/qwen3.8-max")

    async def test_unavailable_model_stops_before_creating_child(self):
        self.agent.agent_config = {"model": "unknown/model"}
        with self.assertRaisesRegex(ValueError, "可用模型目录"):
            await self.create()
        self.conversations.create_conversation.assert_not_awaited()
        self.runs.create_run.assert_not_awaited()
        self.enqueue.assert_not_awaited()
        self.db.rollback.assert_awaited_once()
