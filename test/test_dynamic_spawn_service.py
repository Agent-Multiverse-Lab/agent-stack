"""动态子 Run 的持久化快照、创建者绑定和入队顺序。"""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from server.service import subagent_service, thread_service
from src.agents.library.subagents.general import GENERIC_AGENT, GENERIC_AGENT_SLUG
from src.database.models import Agent, AgentRun, Conversation, Message, User
from src.database.repositories import AgentRepository


class SessionAdapter:
    def __init__(self, session):
        self.session = session

    def add(self, value):
        self.session.add(value)

    async def execute(self, statement, **kwargs):
        return self.session.execute(statement, **kwargs)

    async def flush(self):
        self.session.flush()

    async def commit(self):
        self.session.commit()

    async def rollback(self):
        self.session.rollback()

    async def get(self, entity, key):
        return self.session.get(entity, key)


class DynamicSpawnServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.engine = create_engine(f"sqlite:///{Path(directory.name) / 'spawn.db'}")
        self.addCleanup(self.engine.dispose)
        for model in (User, Agent, Conversation, Message, AgentRun):
            model.__table__.create(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)
        self.addCleanup(self.session.close)
        self.db = SessionAdapter(self.session)
        await AgentRepository(self.db).ensure_agent(
            definition=GENERIC_AGENT, role="subagent", internal_only=True
        )
        self.template = Agent(
            slug="research_template", name="研究模板", role="subagent", is_subagent=True,
            backend_id="SubAgentGraph", internal_only=True, enabled=True,
            agent_config={
                "system_prompt": "返回证据和来源", "model": "deepseek/deepseek-v4-flash",
                "tools": ["web_search"], "mcps": [], "summary_keep_messages": 4,
            },
        )
        self.session.add_all([
            User(uid="user-1", email="spawn@example.com", password_hash="unused"),
            self.template,
        ])
        self.conversation = Conversation(
            uid="user-1", thread_id="parent-thread", agent_id="LeaderAgent", title="Parent"
        )
        self.session.add(self.conversation)
        self.session.flush()
        self.parent = AgentRun(
            id="parent-run", uid="user-1", thread_id="parent-thread",
            conversation_id=self.conversation.id, agent_id="LeaderAgent", run_type="chat",
            agent_status="running", request_id="parent-request",
            run_metadata={"model": "dashscope/qwen3.8-max"},
        )
        self.session.add(self.parent)
        self.session.commit()
        self.service = subagent_service.SubAgentRunService(self.db)

        async def enqueue(run_id):
            # 用另一个数据库连接观察，确保入队之前已提交三类记录。
            with Session(self.engine) as reader:
                run = reader.get(AgentRun, run_id)
                self.assertIsNotNone(run)
                self.assertIsNotNone(reader.get(Conversation, run.conversation_id))
                message = reader.get(Message, run.trigger_message_id)
                self.assertEqual(message.agent_run_id, run.id)

        self.enqueue = AsyncMock(side_effect=enqueue)
        for target, replacement in (
            ("server.service.subagent_service.resolve_runtime_model", AsyncMock()),
            ("server.service.agent_run_service.enqueue_agent_run", self.enqueue),
            ("src.agents.tool_catalog.get_mcp_tools", AsyncMock(return_value=[])),
        ):
            current = patch(target, replacement)
            current.start()
            self.addCleanup(current.stop)

    async def spawn(self, **overrides):
        values = dict(
            created_by_run_id="parent-run", task="比较两个来源", context="仅使用所给材料",
            uid="user-1", tool_call_id="tool-1", request_id="parent-request",
        )
        values.update(overrides)
        return await self.service.create_spawn_record(**values)

    def child(self, record):
        return self.session.get(AgentRun, record["run_id"])

    async def test_without_template_persists_task_and_uses_parent_model_without_tools(self):
        record = await self.spawn()
        run = self.child(record)
        self.assertEqual(run.agent_id, GENERIC_AGENT_SLUG)
        self.assertEqual(run.created_by_run_id, self.parent.id)
        self.assertEqual(run.run_type, "subagent")
        child_conversation = self.session.get(Conversation, run.conversation_id)
        self.assertEqual(child_conversation.parent_conversation_id, self.conversation.id)
        self.assertNotEqual(run.thread_id, self.parent.thread_id)
        self.assertEqual(record["message"]["content"], "任务：\n比较两个来源\n\n上下文：\n仅使用所给材料")
        snapshot = run.run_metadata["spawn"]["agent_config"]
        self.assertIsNone(run.run_metadata["spawn"]["template"])
        self.assertEqual(snapshot["tools"], [])
        self.assertEqual(snapshot["model"], "dashscope/qwen3.8-max")
        self.assertFalse(subagent_service._RUNTIME_IDENTITY_FIELDS & snapshot.keys())
        self.enqueue.assert_awaited_once_with(run.id)

    async def test_template_defaults_and_explicit_empty_override_have_separate_snapshots(self):
        first = self.child(await self.spawn(template=self.template.slug))
        second = self.child(await self.spawn(template=self.template.slug, tools=[], tool_call_id="tool-2"))
        first_config = first.run_metadata["spawn"]["agent_config"]
        second_config = second.run_metadata["spawn"]["agent_config"]
        self.assertEqual(first_config["tools"], ["web_search"])
        self.assertEqual(second_config["tools"], [])
        self.assertEqual(first_config["model"], "deepseek/deepseek-v4-flash")
        self.assertEqual(first_config["summary_keep_messages"], 4)
        self.assertEqual(self.template.agent_config["tools"], ["web_search"])
        self.assertIsNot(first_config["tools"], self.template.agent_config["tools"])

    async def test_explicit_tool_allocation_and_unknown_tool_rejection(self):
        record = await self.spawn(tools=["web_search"])
        self.assertEqual(self.child(record).run_metadata["spawn"]["agent_config"]["tools"], ["web_search"])
        with self.assertRaisesRegex(ValueError, "未找到可分配的工具"):
            await self.spawn(tools=["invented_tool"], tool_call_id="bad-tool")
        self.assertEqual(self.session.scalar(select(func.count()).select_from(AgentRun)), 2)

    async def test_duplicate_tool_call_reuses_persisted_child(self):
        first = await self.spawn()
        second = await self.spawn()
        self.assertEqual(first, second)
        self.assertEqual(self.session.scalar(select(func.count()).select_from(AgentRun)), 2)
        self.assertEqual(self.session.scalar(select(func.count()).select_from(Conversation)), 2)
        self.assertEqual(self.session.scalar(select(func.count()).select_from(Message)), 1)
        self.assertEqual(self.session.scalar(select(func.count()).select_from(Agent)), 2)

    async def test_failed_enqueue_retry_reuses_committed_run(self):
        self.enqueue.side_effect = RuntimeError("queue unavailable")
        with self.assertRaisesRegex(RuntimeError, "queue unavailable"):
            await self.spawn()
        saved_id = self.session.scalar(select(AgentRun.id).where(AgentRun.run_type == "subagent"))
        self.enqueue.side_effect = None
        record = await self.spawn()
        self.assertEqual(record["run_id"], saved_id)
        self.assertEqual(self.session.scalar(select(func.count()).select_from(AgentRun)), 2)

    async def test_creation_rejects_wrong_owner_terminal_parent_and_nested_spawn(self):
        with self.assertRaisesRegex(ValueError, "不属于当前用户"):
            await self.spawn(uid="other-user")
        for status in ("pending", "cancel_requested", "cancelled", "failed", "completed", "interrupted"):
            with self.subTest(status=status):
                self.parent.agent_status = status
                self.session.commit()
                with self.assertRaisesRegex(ValueError, "父运行已停止"):
                    await self.spawn()
        self.parent.agent_status = "running"
        self.parent.run_type = "subagent"
        self.session.commit()
        with self.assertRaisesRegex(ValueError, "不能继续委派"):
            await self.spawn()
        self.assertEqual(self.session.scalar(select(func.count()).select_from(AgentRun)), 1)
        self.enqueue.assert_not_awaited()

    async def test_worker_runtime_uses_snapshot_after_template_and_executor_config_changes(self):
        run = self.child(await self.spawn(template=self.template.slug))
        with Session(self.engine) as reader:
            snapshot = reader.get(AgentRun, run.id).run_metadata["spawn"]["agent_config"]
        self.template.agent_config = {"model": "changed/model", "tools": [], "system_prompt": "Changed"}
        executor = self.session.scalar(select(Agent).where(Agent.slug == GENERIC_AGENT_SLUG))
        executor.agent_config = {"model": "changed/model", "tools": [], "system_prompt": "Changed executor"}
        self.session.commit()
        metadata = {**run.run_metadata, "run_type": "subagent"}
        persisted_config = thread_service._spawn_agent_config(metadata)
        _record, instance, model = await thread_service._build_agent_runtime(
            agent_slug=run.agent_id, user=SimpleNamespace(uid="user-1"), thread_id=run.thread_id,
            db=self.db, run_type="subagent", model=run.run_metadata["model"],
            agent_config_snapshot=persisted_config,
        )
        runtime = await thread_service._build_agent_runtime_context(
            uid="user-1", run_id=run.id, thread_id=run.thread_id, request_id=run.request_id,
            created_by_run_id=run.created_by_run_id, model=model, defaults=persisted_config,
        )
        context = instance.agent_context(**runtime)
        self.assertEqual(context.system_prompt, "返回证据和来源")
        self.assertEqual(context.model, "deepseek/deepseek-v4-flash")
        self.assertEqual(context.uid, run.uid)
        self.assertEqual(context.run_id, run.id)
        self.assertEqual(context.created_by_run_id, self.parent.id)
        context.tools.clear()
        self.assertEqual(run.run_metadata["spawn"]["agent_config"], snapshot)

    async def test_template_cannot_supply_runtime_identity(self):
        self.template.agent_config = {**self.template.agent_config, "uid": "other-user"}
        self.session.commit()
        with self.assertRaisesRegex(ValueError, "不能包含 Run 身份"):
            await self.spawn(template=self.template.slug)
        self.enqueue.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
