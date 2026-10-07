import asyncio
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from server.exception import AgentRunTimeOut
from server.service import agent_run_service, thread_service
from src.agents.agent_library import AgentLibrary
from src.agents.agent_library.leader import LEADER_AGENT
from src.agents.agent_library.subagents import CITATION_AGENT, SEARCH_AGENT
from src.agents.middlewares.subagent_middlware import SubAgentMiddleware
from src.agents.subagents import SubAgentContext, SubAgentGraph
from src.database.models import Agent
from src.database.repositories.agent_repository import AgentRepository


class SessionAdapter:
    """用实际 SQLite SQL 验证 repository，异步入口保持不变。"""

    def __init__(self, session):
        self.session = session

    async def execute(self, statement, **kwargs):
        return self.session.execute(statement, **kwargs)


class AgentConstructionTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        Agent.__table__.create(engine)
        session = Session(engine)
        self.addCleanup(session.close)
        self.db = SessionAdapter(session)
        self.repository = AgentRepository(self.db)
        for definition in (SEARCH_AGENT, CITATION_AGENT):
            await self.repository.sync_agent(definition=definition, role="subagent", internal_only=True)
        await self.repository.sync_agent(definition=LEADER_AGENT)

    async def runtime(self, slug, run_type="subagent"):
        conversations = SimpleNamespace(get_conversation_by_thread_id_for_user=AsyncMock(return_value=object()))
        with patch.object(thread_service, "ConversationRepository", return_value=conversations):
            return await thread_service._build_agent_runtime(
                agent_slug=slug,
                user=SimpleNamespace(uid="user-1"),
                thread_id="thread-1",
                db=self.db,
                run_type=run_type,
            )

    async def test_sync_updates_old_backend_and_preserves_identity_and_disabled_state(self):
        row = await self.repository._get_by_slug(SEARCH_AGENT.slug)
        original_id = row.id
        row.backend_id = "SearchAgent"
        row.enabled = False
        row.agent_config = {}
        self.db.session.flush()
        for _ in range(2):
            updated = await self.repository.sync_agent(definition=SEARCH_AGENT, role="subagent", internal_only=True)
            self.assertEqual(updated.id, original_id)
            self.assertFalse(updated.enabled)
            self.assertEqual(updated.backend_id, "SubAgentGraph")
            self.assertEqual(updated.agent_config, SEARCH_AGENT.context)
        self.assertIsNone(await self.repository.get_by_slug_for_run_type(SEARCH_AGENT.slug, "subagent"))

    async def test_roles_share_class_and_create_new_instances_from_sql_configuration(self):
        _, first = await self.runtime(SEARCH_AGENT.slug)
        _, second = await self.runtime(CITATION_AGENT.slug)
        _, third = await self.runtime(SEARCH_AGENT.slug)
        self.assertIsInstance(first, SubAgentGraph)
        self.assertIs(type(first), type(second))
        self.assertIsNot(first, third)
        self.assertNotEqual(first.definition.context["system_prompt"], second.definition.context["system_prompt"])
        first.definition.context["system_prompt"] = "local mutation"
        _, fresh = await self.runtime(SEARCH_AGENT.slug)
        self.assertEqual(fresh.definition.context, SEARCH_AGENT.context)

    async def test_public_list_and_leader_only_include_enabled_roles(self):
        row = await self.repository._get_by_slug(CITATION_AGENT.slug)
        row.enabled = False
        self.db.session.flush()
        public = await self.repository.list_agents(role="orchestrator", internal_only=False)
        self.assertEqual([item.slug for item in public], [LEADER_AGENT.slug])
        for run_type in ("chat", "resume"):
            _, leader = await self.runtime(LEADER_AGENT.slug, run_type)
            self.assertEqual([item.slug for item in leader.subagents], [SEARCH_AGENT.slug])

    async def test_context_defaults_survive_missing_model_and_do_not_share_nested_values(self):
        defaults = {"model": "preset/model", "mcps": ["configured-server"], "style_profolio": {"a": [1]}}
        values = dict(uid="user-1", run_id="run-1", thread_id="thread-1", request_id="request-1", defaults=defaults)
        first = await thread_service._build_agent_runtime_context(**values, model="")
        second = await thread_service._build_agent_runtime_context(**values, model="chosen/model")
        first["mcps"].append("local")
        first["style_profolio"]["a"].append(2)
        self.assertEqual(first["model"], "preset/model")
        self.assertEqual(second["model"], "chosen/model")
        self.assertEqual(second["mcps"], ["configured-server"])
        self.assertEqual(defaults["style_profolio"], {"a": [1]})

    async def test_unknown_backend_and_context_are_rejected_before_execution(self):
        row = await self.repository._get_by_slug(SEARCH_AGENT.slug)
        row.agent_config = {"unrecognized_field": True}
        self.db.session.flush()
        with self.assertRaisesRegex(ValueError, "未知 Agent Context"):
            await self.runtime(row.slug)
        row.backend_id = "os.system"
        self.db.session.flush()
        with self.assertRaisesRegex(ValueError, "未知 Agent backend"):
            await self.runtime(row.slug)
        with self.assertRaisesRegex(ValueError, "Run 身份"):
            AgentLibrary(slug="bad", name="bad", description="", backend_id="SubAgentGraph", context={"uid": "forged"})

    async def test_common_graph_executes_each_role_with_its_own_prompt_and_checkpoint(self):
        calls = []

        class Model(FakeMessagesListChatModel):
            def bind_tools(self, tools, **kwargs):
                return self

            def _generate(self, messages, *args, **kwargs):
                calls.append(messages)
                return super()._generate(messages, *args, **kwargs)

        checkpointer, store = InMemorySaver(), InMemoryStore()
        model = Model(responses=[AIMessage(content="role result")])
        for definition in (SEARCH_AGENT, CITATION_AGENT):
            _, agent = await self.runtime(definition.slug)
            context = SubAgentContext(uid="user-1", thread_id=definition.slug, run_id=definition.slug)
            context.update_context(agent.definition.context)
            with (
                patch("src.agents.subagents.subagentgraph.get_mcp_tools", AsyncMock(return_value=[])),
                patch("src.agents.subagents.subagentgraph.load_model", return_value=model),
                patch.object(agent, "get_checkpointer", return_value=checkpointer),
                patch.object(agent, "get_store", return_value=store),
            ):
                graph = await agent.get_agent(context)
                config = {"configurable": {"thread_id": context.thread_id}}
                result = await graph.ainvoke({"messages": [HumanMessage(content="task")]}, config, context=context)
                snapshot = await graph.aget_state(config)
            self.assertEqual(result["messages"][-1].content, "role result")
            self.assertEqual(snapshot.values["messages"][-1].content, "role result")
            self.assertIn(definition.context["system_prompt"], calls[-1][0].text)

    async def test_task_and_start_delegate_by_slug_using_parent_run_identity(self):
        middleware = SubAgentMiddleware(
            subagents=[SEARCH_AGENT],
            parent_context=SubAgentContext(uid="user-1", run_id="parent-1", request_id="request-1"),
        )
        service = SimpleNamespace(
            create_subagent_record=AsyncMock(
                return_value={
                    "run_id": "child-1",
                    "thread_id": "child-thread",
                    "status": "pending",
                }
            )
        )
        runtime = SimpleNamespace(tool_call_id="call-1")
        module = "src.agents.middlewares.subagent_middlware"
        with (
            patch(f"{module}.session_context", fake_session),
            patch(f"{module}._subagent_run_service", return_value=service),
            patch(f"{module}.wait_agent_run_result", AsyncMock(return_value="child result")) as wait,
        ):
            task = next(tool for tool in middleware.tools if tool.name == "task")
            result = await task.coroutine(description="verify sources", subagent_slug=SEARCH_AGENT.slug, runtime=runtime)
            self.assertEqual(result.update["messages"][0].content, "child result")
            wait.assert_awaited_once_with("child-1", uid="user-1")
            start = next(tool for tool in middleware.tools if tool.name == "subagent_start")
            result = await start.coroutine(description="search", subagent_slug=SEARCH_AGENT.slug, runtime=runtime)
            self.assertEqual(result.update["messages"][0].additional_kwargs["subagent_status"], "pending")
            self.assertEqual(wait.await_count, 1)
        values = service.create_subagent_record.await_args.kwargs
        self.assertEqual((values["agent_slug"], values["parent_run_id"], values["uid"]), (SEARCH_AGENT.slug, "parent-1", "user-1"))


@asynccontextmanager
async def fake_session():
    yield object()


class AgentResultWaitTest(unittest.IsolatedAsyncioTestCase):
    async def test_wait_uses_sql_terminal_state_and_advances_event_cursor(self):
        repository = SimpleNamespace(
            get_by_id_for_user=AsyncMock(
                side_effect=[
                    SimpleNamespace(agent_status="running", error=None),
                    SimpleNamespace(agent_status="running", error=None),
                    SimpleNamespace(agent_status="completed", error=None),
                ]
            )
        )
        with (
            patch.object(agent_run_service, "session_context", fake_session),
            patch.object(agent_run_service, "AgentRunRepository", return_value=repository),
            patch.object(agent_run_service, "read_agent_run_events", AsyncMock(side_effect=[[("1-0", {})], [("2-0", {})]])) as events,
            patch.object(agent_run_service, "get_agent_run_result", AsyncMock(return_value="verified result")) as result,
        ):
            self.assertEqual(await agent_run_service.wait_agent_run_result("child-1", "user-1"), "verified result")
        self.assertEqual(events.await_args_list[1].kwargs["after_id"], "1-0")
        result.assert_awaited_once_with(current_uid="user-1", run_id="child-1")
        self.assertEqual(repository.get_by_id_for_user.await_args.kwargs["uid"], "user-1")

    async def test_failure_timeout_and_cancellation_do_not_become_completed(self):
        repository = SimpleNamespace(get_by_id_for_user=AsyncMock(return_value=SimpleNamespace(agent_status="failed", error="failed task")))
        with (
            patch.object(agent_run_service, "session_context", fake_session),
            patch.object(agent_run_service, "AgentRunRepository", return_value=repository),
            patch.object(agent_run_service, "read_agent_run_events", AsyncMock(side_effect=asyncio.CancelledError)),
        ):
            with self.assertRaisesRegex(RuntimeError, "failed"):
                await agent_run_service.wait_agent_run_result("child-1", "user-1")
            repository.get_by_id_for_user.return_value = SimpleNamespace(agent_status="running", error=None)
            with self.assertRaises(AgentRunTimeOut):
                await agent_run_service.wait_agent_run_result("child-1", "user-1", time_out=0)
            with self.assertRaises(asyncio.CancelledError):
                await agent_run_service.wait_agent_run_result("child-1", "user-1")


if __name__ == "__main__":
    unittest.main()
