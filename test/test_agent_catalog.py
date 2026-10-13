"""数据库 Agent 目录的分组、认证和摘要边界。"""

import unittest
from types import SimpleNamespace

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from server.router.agent_router import agent_router
from server.utils.auth import get_current_user
from src.database import get_db
from src.database.models import Agent
from src.database.repositories.agent_repository import AgentRepository


class SessionAdapter:
    """通过同步 SQLite Session 执行仓储的实际 SQL。"""

    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)

    async def commit(self):
        self.session.commit()

    async def refresh(self, instance):
        self.session.refresh(instance)


class AgentCatalogTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        self.engine = engine
        Agent.__table__.create(engine)
        session = Session(engine)
        self.addCleanup(session.close)
        self.db = SessionAdapter(session)
        self.repository = AgentRepository(self.db)
        records = (
            ("z_disabled_child", True, True, False),
            ("Z_disabled_main", False, True, False),
            ("LeaderAgent", False, False, True),
            ("m_internal_child", True, True, True),
            ("A_database_main", False, True, True),
            ("a_public_child", True, False, True),
        )
        for slug, is_subagent, internal_only, enabled in records:
            session.add(
                Agent(
                    slug=slug,
                    backend_id="SubAgentGraph" if is_subagent else "LeaderAgent",
                    name=f"数据库名称 {slug}",
                    description=f"数据库描述 {slug}",
                    role="subagent" if is_subagent else "orchestrator",
                    is_subagent=is_subagent,
                    internal_only=internal_only,
                    enabled=enabled,
                    agent_config={"system_prompt": "private-system-prompt"},
                )
            )
        session.flush()

    def create_app(self, *, authenticated=False):
        async def override_db():
            return self.db

        async def override_user():
            return SimpleNamespace(id=1, uid="user-1")

        app = FastAPI()
        app.include_router(agent_router, prefix="/api")
        app.dependency_overrides[get_db] = override_db
        if authenticated:
            app.dependency_overrides[get_current_user] = override_user
        return app

    async def test_sql_catalog_groups_all_records_without_changing_run_filters(self):
        agents = await self.repository.list_main_agents()
        subagents = await self.repository.list_subagents()
        self.assertEqual([row.slug for row in agents], ["A_database_main", "LeaderAgent", "Z_disabled_main"])
        self.assertEqual([row.slug for row in subagents], ["a_public_child", "m_internal_child", "z_disabled_child"])
        self.assertTrue(all(not row.is_subagent for row in agents))
        self.assertTrue(all(row.is_subagent for row in subagents))
        self.assertFalse(agents[-1].enabled)
        self.assertFalse(subagents[-1].enabled)
        self.assertTrue(subagents[1].internal_only)

        public = await self.repository.list_agents(role="orchestrator", internal_only=False)
        self.assertEqual([row.slug for row in public], ["LeaderAgent"])
        self.assertIsNone(await self.repository.get_by_slug_for_run_type("Z_disabled_main"))
        self.assertIsNone(await self.repository.get_by_slug_for_run_type("z_disabled_child", "subagent"))
        self.assertIsNone(await self.repository.get_by_slug_for_run_type("m_internal_child", "chat"))
        self.assertIsNotNone(await self.repository.get_by_slug_for_run_type("m_internal_child", "subagent"))

    async def test_catalog_requires_authentication_and_returns_database_summaries(self):
        app = self.create_app()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            self.assertEqual((await client.get("/api/agent/catalog")).status_code, 401)
        app = self.create_app(authenticated=True)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            response = await client.get("/api/agent/catalog")
        self.assertEqual(response.status_code, 200)
        catalog = response.json()
        self.assertEqual(set(catalog), {"agents", "subagents"})
        self.assertEqual([row["id"] for row in catalog["agents"]], ["A_database_main", "LeaderAgent", "Z_disabled_main"])
        self.assertEqual([row["id"] for row in catalog["subagents"]], ["a_public_child", "m_internal_child", "z_disabled_child"])
        for group, is_subagent in (("agents", False), ("subagents", True)):
            for row in catalog[group]:
                self.assertEqual(set(row), {"id", "name", "description", "is_subagent", "enabled"})
                self.assertEqual(row["name"], f"数据库名称 {row['id']}")
                self.assertEqual(row["description"], f"数据库描述 {row['id']}")
                self.assertEqual(row["is_subagent"], is_subagent)
        self.assertFalse(catalog["agents"][-1]["enabled"])
        self.assertFalse(catalog["subagents"][-1]["enabled"])
        self.assertNotIn("private-system-prompt", response.text)
        self.assertNotIn("agent_config", response.text)
        self.assertNotIn("backend_id", response.text)

    async def test_empty_database_returns_empty_catalog_groups(self):
        self.db.session.query(Agent).delete()
        self.db.session.flush()
        app = self.create_app(authenticated=True)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            response = await client.get("/api/agent/catalog")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"agents": [], "subagents": []})

    async def test_partial_update_persists_and_preserves_role_and_configuration(self):
        row = await self.repository._get_by_slug("z_disabled_child")
        protected_fields = (
            "id", "slug", "backend_id", "role", "is_subagent", "internal_only", "agent_config", "created_at",
        )
        original = {field: getattr(row, field) for field in protected_fields}
        app = self.create_app(authenticated=True)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            response = await client.patch("/api/agent/z_disabled_child", json={"name": "  修改后的子 Agent  "})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.json(),
                {
                    "id": "z_disabled_child",
                    "name": "修改后的子 Agent",
                    "description": "数据库描述 z_disabled_child",
                    "is_subagent": True,
                    "enabled": False,
                },
            )
            catalog = (await client.get("/api/agent/catalog")).json()
            saved = next(item for item in catalog["subagents"] if item["id"] == "z_disabled_child")
            self.assertEqual(saved, response.json())
            response = await client.patch("/api/agent/z_disabled_child", json={"description": "", "enabled": True})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["name"], "修改后的子 Agent")
            self.assertEqual(response.json()["description"], "")
            self.assertTrue(response.json()["enabled"])
            self.assertNotIn("private-system-prompt", response.text)

        with Session(self.engine) as observer:
            persisted = observer.get(Agent, original["id"])
            self.assertEqual(persisted.name, "修改后的子 Agent")
            self.assertEqual(persisted.description, "")
            self.assertTrue(persisted.enabled)
            self.assertEqual({field: getattr(persisted, field) for field in protected_fields}, original)

    async def test_top_level_and_database_only_agents_can_be_updated(self):
        app = self.create_app(authenticated=True)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            response = await client.patch(
                "/api/agent/LeaderAgent",
                json={"name": "数据库主 Agent", "description": "修改后的主 Agent 描述", "enabled": False},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["name"], "数据库主 Agent")
            self.assertFalse(response.json()["is_subagent"])
            self.assertFalse(response.json()["enabled"])
            response = await client.patch("/api/agent/A_database_main", json={"name": "仅数据库中的 Agent"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["name"], "仅数据库中的 Agent")
            self.assertTrue(response.json()["enabled"])

        self.assertIsNone(await self.repository.get_by_slug_for_run_type("LeaderAgent"))
        self.assertEqual(await self.repository.list_agents(role="orchestrator", internal_only=False), [])
        with Session(self.engine) as observer:
            rows = {row.slug: row for row in observer.query(Agent).all()}
            self.assertEqual(rows["LeaderAgent"].description, "修改后的主 Agent 描述")
            self.assertEqual(rows["A_database_main"].name, "仅数据库中的 Agent")
            self.assertEqual(rows["A_database_main"].description, "数据库描述 A_database_main")

    async def test_updates_require_authentication_and_missing_agent_returns_404(self):
        app = self.create_app()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            response = await client.patch("/api/agent/LeaderAgent", json={"name": "拒绝未认证修改"})
            self.assertEqual(response.status_code, 401)
        app = self.create_app(authenticated=True)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            response = await client.patch("/api/agent/missing_agent", json={"enabled": False})
            self.assertEqual(response.status_code, 404)
        self.assertEqual((await self.repository._get_by_slug("LeaderAgent")).name, "数据库名称 LeaderAgent")
        self.assertIsNone(await self.repository._get_by_slug("missing_agent"))

    async def test_invalid_and_structural_updates_are_rejected_without_mutation(self):
        app = self.create_app(authenticated=True)
        invalid = [
            {}, {"name": None}, {"description": None}, {"enabled": None},
            {"name": ""}, {"name": "  \t\n  "}, {"name": "x" * 129},
            {"name": 123}, {"description": 123}, {"enabled": "false"}, {"enabled": 1},
        ]
        for field, value in (
            ("id", "forged"), ("slug", "forged"), ("role", "orchestrator"),
            ("is_subagent", False), ("backend_id", "LeaderAgent"), ("internal_only", False),
            ("agent_config", {"system_prompt": "forged"}), ("unknown", "forged"),
        ):
            invalid.append({"name": "不可保存的名称", field: value})
        row = await self.repository._get_by_slug("m_internal_child")
        original = {column.name: getattr(row, column.name) for column in Agent.__table__.columns}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            for payload in invalid:
                with self.subTest(payload=payload):
                    response = await client.patch("/api/agent/m_internal_child", json=payload)
                    self.assertEqual(response.status_code, 422)
        self.db.session.expire_all()
        persisted = await self.repository._get_by_slug("m_internal_child")
        self.assertEqual({column.name: getattr(persisted, column.name) for column in Agent.__table__.columns}, original)
