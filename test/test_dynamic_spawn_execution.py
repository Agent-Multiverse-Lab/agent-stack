"""动态委派从工具、SQL 快照到执行图及结果查询的集成验证。"""

import json
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from server.service import thread_service
from src.agents.base_context import BaseContext
from src.agents.library.subagents import GENERIC_AGENT
from src.agents.middlewares.subagent_middlware import SubAgentMiddleware
from src.database.models import Agent, AgentRun, AgentRunAttempt, Conversation, Message, User
from src.database.repositories import AgentRepository, ConversationRepository


class SessionAdapter:
    """保留实际 SQL 和事务，仅适配仓储的异步接口。"""

    def __init__(self, session):
        self.session = session

    def add(self, value):
        self.session.add(value)

    async def execute(self, statement, **kwargs):
        return self.session.execute(statement, **kwargs)

    async def get(self, model, key):
        return self.session.get(model, key)

    async def flush(self):
        self.session.flush()

    async def commit(self):
        self.session.commit()

    async def rollback(self):
        self.session.rollback()


class ToolCallingModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self

    async def _agenerate(self, messages, *args, **kwargs):
        return self._generate(messages, *args, **kwargs)


class DynamicSpawnExecutionTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        AgentRun.metadata.create_all(engine, tables=[
            User.__table__, Agent.__table__, Conversation.__table__, Message.__table__,
            AgentRun.__table__, AgentRunAttempt.__table__,
        ])
        self.session = Session(engine, expire_on_commit=False)
        self.addCleanup(self.session.close)
        self.db = SessionAdapter(self.session)
        self.user = User(uid="user-1", email="spawn@example.test", password_hash="unused")
        self.session.add(self.user)
        self.session.flush()
        await AgentRepository(self.db).ensure_agent(
            definition=GENERIC_AGENT, role="subagent", internal_only=True,
        )
        self.template = Agent(
            slug="evidence_template", name="证据核验", description="核验分配的材料",
            backend_id="SubAgentGraph", role="subagent", is_subagent=True,
            internal_only=True, enabled=True,
            agent_config={
                "system_prompt": "按提供的来源回答，并保留证据编号。",
                "model": "test/original", "tools": ["web_search"],
            },
        )
        self.session.add(self.template)
        conversation = await ConversationRepository(self.db).create_conversation(
            uid=self.user.uid, thread_id="parent-thread", agent_slug="leader_agent",
        )
        await ConversationRepository(self.db).create_agent_input_message(
            conversation_id=conversation.id, content="父会话独有内容，不分配给子任务",
        )
        self.parent = AgentRun(
            id="parent-run", uid=self.user.uid, thread_id=conversation.thread_id,
            conversation_id=conversation.id, agent_id="leader_agent", run_type="chat",
            agent_status="running", run_metadata={"model": "test/parent"},
        )
        self.session.add(self.parent)
        self.session.commit()
        self.parent_context = BaseContext(
            uid=self.user.uid, thread_id=conversation.thread_id, run_id=self.parent.id,
            request_id="parent-request", model="test/parent", system_prompt="父代理指令",
        )
        self.middleware = SubAgentMiddleware(
            subagents=[{"slug": self.template.slug, "name": self.template.name, "description": self.template.description}],
            parent_context=self.parent_context,
        )
        self.tools = {tool.name: tool for tool in self.middleware.tools}

        @asynccontextmanager
        async def session_context():
            yield self.db

        for target, value in (
            ("src.agents.middlewares.subagent_middlware.session_context", session_context),
            ("server.service.agent_run_service.session_context", session_context),
            ("server.service.subagent_service.resolve_runtime_model", AsyncMock()),
            ("server.service.agent_run_service.enqueue_agent_run", AsyncMock()),
            ("server.service.agent_run_service.read_recent_agent_run_stream_events", AsyncMock(return_value=[])),
            ("server.service.agent_run_service.publish_agent_run_cancel_signal", AsyncMock()),
        ):
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    async def spawn(self, call_id="spawn-1", **kwargs):
        model = ToolCallingModel(responses=[
            AIMessage(content="", tool_calls=[{"name": "spawn_agent", "args": kwargs, "id": call_id}]),
            AIMessage(content="子任务已委派。"),
        ])
        graph = create_agent(
            model=model, middleware=[self.middleware], context_schema=BaseContext,
        )
        state = await graph.ainvoke(
            {"messages": [HumanMessage(content="执行独立子任务")]}, context=self.parent_context,
        )
        message = next(message for message in state["messages"] if isinstance(message, ToolMessage))
        self.assertEqual(message.status, "success", message.content)
        record = json.loads(message.content)
        return self.session.get(AgentRun, record["run_id"])

    async def test_persisted_assignment_survives_template_changes_and_executes_selected_tools(self):
        calls = []

        async def lookup(query: str) -> str:
            return f"证据 source-7：{query} 已核验"

        lookup_tool = StructuredTool.from_function(
            name="web_search", description="查询证据夹具", coroutine=lookup,
        )

        class Model(ToolCallingModel):
            def _generate(self, messages, *args, **kwargs):
                calls.append(messages)
                return super()._generate(messages, *args, **kwargs)

        with patch("src.agents.tool_catalog.web_search", lookup_tool):
            run = await self.spawn(
                task="核验卫星拍摄日期", context="给定证据 source-7，目标影像编号 image-42",
                template=self.template.slug,
            )
            snapshot = thread_service._spawn_agent_config({**run.run_metadata, "run_type": run.run_type})
            original_prompt = snapshot["system_prompt"]
            original_tools = list(snapshot["tools"])
            self.assertEqual(run.agent_id, GENERIC_AGENT.slug)
            self.assertEqual(run.created_by_run_id, self.parent.id)
            self.assertNotEqual(run.thread_id, self.parent.thread_id)
            self.assertNotEqual(run.id, self.parent.id)

            self.template.agent_config = {
                "system_prompt": "修改后的模板", "tools": [], "model": "test/changed",
            }
            self.parent_context.system_prompt = "修改后的父代理指令"
            self.parent_context.tools = ["execute"]
            self.session.commit()
            self.session.expire_all()
            run = self.session.get(AgentRun, run.id)
            snapshot = thread_service._spawn_agent_config({**run.run_metadata, "run_type": run.run_type})
            _, instance, model_id = await thread_service._build_agent_runtime(
                agent_slug=run.agent_id, user=self.user, thread_id=run.thread_id,
                db=self.db, run_type=run.run_type, model=run.run_metadata["model"],
                agent_config_snapshot=snapshot,
            )
            runtime = await thread_service._build_agent_runtime_context(
                uid=run.uid, run_id=run.id, thread_id=run.thread_id, request_id=run.request_id,
                model=model_id, defaults=snapshot, created_by_run_id=run.created_by_run_id,
            )
            context = instance.agent_context()
            context.update_context(runtime)
            self.assertEqual(context.system_prompt, original_prompt)
            self.assertEqual(context.tools, original_tools)
            self.assertEqual(context.model, "test/original")
            self.assertEqual(context.run_id, run.id)
            model = Model(responses=[
                AIMessage(content="", tool_calls=[
                    {"name": "web_search", "args": {"query": "image-42 拍摄日期"}, "id": "lookup-1"},
                    {"name": "execute", "args": {"command": "echo unassigned"}, "id": "forbidden-1"},
                ]),
                AIMessage(content="已核验 image-42，依据 source-7。"),
            ])
            input_message = self.session.get(Message, run.trigger_message_id)
            with (
                patch("src.agents.buildin.subagents.subagent_graph.load_chat_model", AsyncMock(return_value=model)),
                patch.object(instance, "get_checkpointer", return_value=InMemorySaver()),
                patch.object(instance, "get_store", return_value=InMemoryStore()),
            ):
                graph = await instance.get_agent(context)
                result = await graph.ainvoke(
                    {"messages": [HumanMessage(content=input_message.content)]},
                    {"configurable": {"thread_id": run.thread_id}}, context=context,
                )

        tool_results = {message.tool_call_id: message for message in result["messages"] if isinstance(message, ToolMessage)}
        self.assertEqual(tool_results["lookup-1"].content, "证据 source-7：image-42 拍摄日期 已核验")
        self.assertEqual(tool_results["forbidden-1"].status, "error")
        self.assertIn("未分配工具", tool_results["forbidden-1"].content)
        self.assertIn(original_prompt, calls[0][0].text)
        human_messages = [message.content for message in calls[0] if isinstance(message, HumanMessage)]
        self.assertEqual(human_messages, ["任务：\n核验卫星拍摄日期\n\n上下文：\n给定证据 source-7，目标影像编号 image-42"])
        self.assertEqual(snapshot["tools"], ["web_search"])

        output = await ConversationRepository(self.db).create_agent_output_message(
            conversation_id=run.conversation_id, agent_run_id=run.id,
            content=result["messages"][-1].content,
        )
        run.output_message_id = output.id
        run.agent_status = "completed"
        self.session.commit()
        status = json.loads(await self.tools["subagent_status"].coroutine(run_id=run.id))
        self.assertEqual(status["status"], "completed")
        self.assertEqual(status["result"], output.content)
        awaited = await self.tools["subagent_await"].coroutine(
            run_id=run.id, runtime=SimpleNamespace(tool_call_id="await-1"),
        )
        self.assertEqual(awaited.update["messages"][0].content, output.content)

    async def test_untemplated_spawn_uses_no_tools_and_existing_cancel_protocol(self):
        run = await self.spawn(task="总结已经提供的结论", context="结论：观测完成")
        repeated = await self.spawn(task="总结已经提供的结论", context="结论：观测完成")
        self.assertEqual(repeated.id, run.id)
        self.assertEqual(len(self.session.scalars(select(AgentRun)).all()), 2)
        self.assertEqual(run.run_metadata["spawn"]["agent_config"]["tools"], [])
        self.assertEqual(run.run_metadata["model"], "test/parent")
        self.assertEqual(len(self.session.scalars(select(Agent)).all()), 2)
        command = await self.tools["subagent_cancel"].coroutine(
            run_id=run.id, runtime=SimpleNamespace(tool_call_id="cancel-1"),
        )
        message = command.update["messages"][0]
        self.assertEqual(message.status, "success", message.content)
        self.session.expire_all()
        self.assertEqual(self.session.get(AgentRun, run.id).agent_status, "cancel_requested")
        self.assertEqual(self.session.get(AgentRun, self.parent.id).agent_status, "running")


if __name__ == "__main__":
    unittest.main()
