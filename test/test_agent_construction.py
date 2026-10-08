import asyncio
import importlib.util
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import src.agents.buildin as agent
from server import worker
from server.exception import AgentRunTimeOut
from server.service import agent_run_service, thread_service
from src.agents.agent_library import AgentLibrary
from src.agents.agent_library.leader import LEADER_AGENT
from src.agents.agent_library.subagents import CITATION_AGENT, SEARCH_AGENT, SUBAGENTS
from src.agents.base_agent import BaseAgent
from src.agents.buildin.leader.agent import LeaderAgent
from src.agents.buildin.subagents import SubAgentContext, SubAgentGraph
from src.agents.middlewares.subagent_middlware import SubAgentMiddleware
from src.database.models import Agent
from src.database.repositories.agent_repository import AgentRepository


class SessionAdapter:
    """用实际 SQLite SQL 验证 repository，异步入口保持不变。"""

    def __init__(self, session):
        self.session = session

    async def execute(self, statement, **kwargs):
        return self.session.execute(statement, **kwargs)


class AgentClassTest(unittest.TestCase):
    def test_resolve_exact_backend_class_names(self):
        for expected in (LeaderAgent, SubAgentGraph):
            resolved = agent.get_agent_class(expected.__name__)
            self.assertIs(resolved, expected)
            self.assertTrue(issubclass(resolved, BaseAgent))
        for backend_id in ("", "leaderagent", "search_agent", "os.system", "UnknownAgent"):
            with self.subTest(backend_id=backend_id), self.assertRaisesRegex(ValueError, "未知 Agent backend"):
                agent.get_agent_class(backend_id)


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
            await self.repository.ensure_agent(definition=definition, role="subagent", internal_only=True)
        await self.repository.ensure_agent(definition=LEADER_AGENT)

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

    async def test_worker_creates_missing_agents_and_preserves_all_existing_fields(self):
        existing = {}
        for definition in (SEARCH_AGENT, LEADER_AGENT):
            row = await self.repository._get_by_slug(definition.slug)
            row.name = f"custom {definition.slug}"
            row.description = "database description"
            row.agent_config = {"system_prompt": "database prompt", "model": "custom/model"}
            row.backend_id = "LeaderAgent" if definition is SEARCH_AGENT else "SubAgentGraph"
            row.role = "orchestrator" if definition is SEARCH_AGENT else "subagent"
            row.is_subagent = row.role == "subagent"
            row.internal_only = row.is_subagent
            row.enabled = definition is LEADER_AGENT
        self.db.session.flush()
        for definition in (SEARCH_AGENT, LEADER_AGENT):
            row = await self.repository._get_by_slug(definition.slug)
            existing[row.slug] = {column.name: getattr(row, column.name) for column in Agent.__table__.columns}

        @asynccontextmanager
        async def session_context():
            yield self.db

        expected_slugs = {LEADER_AGENT.slug, *(definition.slug for definition in SUBAGENTS)}
        with patch.object(worker.postgres_manager, "get_async_session_context", session_context):
            for _ in range(2):
                await worker.ensure_agents_exist()
                self.db.session.expire_all()
                rows = self.db.session.execute(select(Agent)).scalars().all()
                self.assertEqual({row.slug for row in rows}, expected_slugs)
                self.assertEqual(len(rows), len(expected_slugs))
                for row in rows:
                    if row.slug in existing:
                        self.assertEqual(
                            {column.name: getattr(row, column.name) for column in Agent.__table__.columns},
                            existing[row.slug],
                        )
                for definition in SUBAGENTS:
                    if definition.slug in existing:
                        continue
                    row = await self.repository._get_by_slug(definition.slug)
                    self.assertEqual(row.backend_id, definition.backend_id)
                    self.assertEqual(row.name, definition.name)
                    self.assertEqual(row.description, definition.description)
                    self.assertEqual(row.agent_config, definition.context)
                    self.assertEqual(row.role, "subagent")
                    self.assertTrue(row.is_subagent)
                    self.assertTrue(row.internal_only)
                    self.assertTrue(row.enabled)

    async def test_roles_share_class_and_create_new_instances_from_sql_configuration(self):
        first_record, first = await self.runtime(SEARCH_AGENT.slug)
        second_record, second = await self.runtime(CITATION_AGENT.slug)
        _, third = await self.runtime(SEARCH_AGENT.slug)
        self.assertIsInstance(first, SubAgentGraph)
        self.assertIs(type(first), type(second))
        self.assertIsNot(first, third)
        self.assertTrue(first_record.is_subagent)
        self.assertTrue(second_record.is_subagent)
        self.assertNotEqual(first_record.agent_config["system_prompt"], second_record.agent_config["system_prompt"])
        context = await thread_service._build_agent_runtime_context(
            uid="user-1", run_id="run-1", thread_id="thread-1", request_id="request-1",
            defaults=first_record.agent_config,
        )
        context["system_prompt"] = "local mutation"
        fresh_record, _ = await self.runtime(SEARCH_AGENT.slug)
        self.assertEqual(fresh_record.agent_config, SEARCH_AGENT.context)

    async def test_public_list_and_leader_only_include_enabled_roles(self):
        row = await self.repository._get_by_slug(CITATION_AGENT.slug)
        row.enabled = False
        self.db.session.flush()
        public = await self.repository.list_agents(role="orchestrator", internal_only=False)
        self.assertEqual([item.slug for item in public], [LEADER_AGENT.slug])
        self.assertFalse(public[0].is_subagent)
        for run_type in ("chat", "resume"):
            _, leader = await self.runtime(LEADER_AGENT.slug, run_type)
            self.assertEqual([item["slug"] for item in leader.subagents], [SEARCH_AGENT.slug])

    async def test_runtime_uses_database_attributes_without_agent_library(self):
        custom = Agent(
            slug="database_only_agent", backend_id="SubAgentGraph", name="数据库子角色",
            description="数据库中的子角色描述", role="subagent", is_subagent=True,
            internal_only=True, enabled=True, agent_config={"system_prompt": "数据库中的 Prompt"},
        )
        self.db.session.add(custom)
        leader_record = await self.repository._get_by_slug(LEADER_AGENT.slug)
        leader_record.name = "数据库中的主角色"
        leader_record.description = "数据库中的主角色描述"
        self.db.session.flush()

        with patch.object(AgentLibrary, "__post_init__", side_effect=AssertionError("runtime used AgentLibrary")):
            _, leader = await self.runtime(LEADER_AGENT.slug, "chat")
            record, child = await self.runtime(custom.slug)
            self.assertEqual(leader.name, leader_record.name)
            self.assertEqual(leader.description, leader_record.description)
            self.assertIn(
                {"slug": custom.slug, "name": custom.name, "description": custom.description},
                leader.subagents,
            )
            middleware = SubAgentMiddleware(subagents=leader.subagents, parent_context=SubAgentContext())
            self.assertIn("- database_only_agent (数据库子角色): 数据库中的子角色描述", middleware._system_prompt())
            self.assertIsInstance(child, SubAgentGraph)
            context = await thread_service._build_agent_runtime_context(
                uid="user-1", run_id="child-1", thread_id="child-thread", request_id="request-1",
                defaults=record.agent_config,
            )
            self.assertEqual(context["system_prompt"], "数据库中的 Prompt")
            leader.subagents[0]["description"] = "local mutation"
            _, fresh = await self.runtime(LEADER_AGENT.slug, "resume")
            self.assertNotEqual(fresh.subagents[0]["description"], "local mutation")

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

    async def test_runtime_context_freezes_default_model_and_overrides_run_identity(self):
        values = dict(uid="user-1", run_id="run-1", thread_id="thread-1", request_id="request-1")
        with patch.object(thread_service.config, "default_model", "configured/model"):
            context = await thread_service._build_agent_runtime_context(
                **values, defaults={"uid": "ignored", "model": ""}, parent_run_id="parent-1",
            )
        with patch.object(thread_service.config, "default_model", "changed/model"):
            self.assertEqual(context["model"], "configured/model")
            agent_context = SubAgentContext()
            agent_context.update_context(context)
            self.assertEqual(agent_context.model, "configured/model")
        self.assertEqual(context["uid"], "user-1")
        self.assertEqual(context["parent_run_id"], "parent-1")

    async def test_unknown_backend_and_context_are_rejected_before_execution(self):
        row = await self.repository._get_by_slug(SEARCH_AGENT.slug)
        for config, error in (
            ({"unrecognized_field": True}, "未知 Agent Context"),
            ({"uid": "forged"}, "Run 身份"),
            ({"parent_run_id": "forged"}, "Run 身份"),
            ([], "配置必须是字典"),
            ({"summary_threshold": float("nan")}, "JSON compliant"),
        ):
            with self.subTest(config=config):
                row.agent_config = config
                self.db.session.flush()
                with self.assertRaisesRegex(ValueError, error):
                    await self.runtime(row.slug)
        row.backend_id = "os.system"
        self.db.session.flush()
        with self.assertRaisesRegex(ValueError, "未知 Agent backend"):
            await self.runtime(row.slug)
        with self.assertRaisesRegex(ValueError, "Run 身份"):
            AgentLibrary(slug="bad", name="bad", description="", backend_id="SubAgentGraph", context={"uid": "forged"})

    async def test_role_flags_must_match_backend(self):
        row = await self.repository._get_by_slug(SEARCH_AGENT.slug)
        row.is_subagent = False
        self.db.session.flush()
        with self.assertRaisesRegex(ValueError, "配置不一致"):
            await self.runtime(row.slug)

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
            record, agent = await self.runtime(definition.slug)
            context = SubAgentContext(uid="user-1", thread_id=definition.slug, run_id=definition.slug)
            context.update_context(record.agent_config)
            with (
                patch("src.agents.buildin.subagents.subagent_graph.get_mcp_tools", AsyncMock(return_value=[])),
                patch("src.agents.buildin.subagents.subagent_graph.load_model", return_value=model),
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
            subagents=[{"slug": SEARCH_AGENT.slug, "name": SEARCH_AGENT.name, "description": SEARCH_AGENT.description}],
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


class AgentSubagentMigrationTest(unittest.TestCase):
    def test_upgrade_backfills_roles_and_downgrade_preserves_existing_data(self):
        path = Path(__file__).resolve().parents[1] / "migrate/versions/0014_agent_is_subagent.py"
        spec = importlib.util.spec_from_file_location("agent_is_subagent_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        with engine.begin() as connection:
            connection.execute(text(
                "CREATE TABLE agent (id INTEGER PRIMARY KEY, slug TEXT NOT NULL, "
                "role TEXT NOT NULL, enabled BOOLEAN NOT NULL)"
            ))
            connection.execute(text(
                "INSERT INTO agent (id, slug, role, enabled) VALUES "
                "(1, 'LeaderAgent', 'orchestrator', 1), "
                "(2, 'search_agent', 'subagent', 1), "
                "(3, 'disabled_subagent', 'subagent', 0), "
                "(4, 'disabled_leader', 'orchestrator', 0)"
            ))
            original = connection.execute(text("SELECT id, slug, role, enabled FROM agent ORDER BY id")).all()
            with patch.object(migration, "op", Operations(MigrationContext.configure(connection))):
                migration.upgrade()
                column = next(item for item in inspect(connection).get_columns("agent") if item["name"] == "is_subagent")
                self.assertFalse(column["nullable"])
                self.assertEqual(
                    connection.execute(text("SELECT id, is_subagent FROM agent ORDER BY id")).all(),
                    [(1, False), (2, True), (3, True), (4, False)],
                )
                connection.execute(text(
                    "INSERT INTO agent (id, slug, role, enabled) VALUES (5, 'new_leader', 'orchestrator', 1)"
                ))
                self.assertEqual(connection.execute(text("SELECT is_subagent FROM agent WHERE id = 5")).scalar_one(), False)
                with self.assertRaises(IntegrityError):
                    connection.execute(text(
                        "INSERT INTO agent (id, slug, role, enabled, is_subagent) "
                        "VALUES (6, 'invalid', 'orchestrator', 1, NULL)"
                    ))
                migration.downgrade()
                self.assertEqual(
                    {item["name"] for item in inspect(connection).get_columns("agent")},
                    {"id", "slug", "role", "enabled"},
                )
                self.assertEqual(
                    connection.execute(text("SELECT id, slug, role, enabled FROM agent WHERE id <= 4 ORDER BY id")).all(),
                    original,
                )


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
