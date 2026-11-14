"""Project HTTP 契约、真实 Repository SQL 与迁移验证。"""

import importlib.util
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from sqlalchemy.orm import Session

from server.router.project_router import router as project_router
from server.router.thread_router import router as thread_router
from server.service import thread_service
from server.utils.auth import get_current_user
from src.database import get_db
from src.database.models import AgentRun, Conversation, Message, Project, SubAgentConversationRelation
from src.database.repositories import ConversationRepository, ProjectRepository
from test.test_subagent_conversation_relation import AsyncSessionAdapter


class ChatProjectsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = sa.create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        for model in (Project, Conversation, AgentRun, Message, SubAgentConversationRelation):
            model.__table__.create(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)
        self.addCleanup(self.session.close)
        self.db = AsyncSessionAdapter(self.session)
        self.projects = ProjectRepository(self.db)
        self.conversations = ConversationRepository(self.db)
        self.app = FastAPI()
        self.app.include_router(project_router, prefix="/api")
        self.app.include_router(thread_router, prefix="/api")
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(uid="user-1")

    async def conversation(self, uid="user-1", project_id=None):
        count = self.session.query(Conversation).count()
        return await self.conversations.create_conversation(
            uid=uid, thread_id=f"thread-{count}", agent_slug="leader", title=f"Thread {count}", project_id=project_id,
        )

    async def test_project_crud_thread_binding_and_user_isolation(self):
        conversation = await self.conversation()
        foreign = await self.projects.create("user-2", "Other user")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test") as client:
            self.assertEqual(422, (await client.post("/api/projects", json={"name": "  "})).status_code)
            created = await client.post("/api/projects", json={"name": "  Research  "})
            self.assertEqual(200, created.status_code)
            project = created.json()
            self.assertNotIn("id", project)
            self.assertTrue(project["project_id"])
            self.assertEqual("Research", project["name"])
            self.assertFalse(project["pinned"])
            path = f'/api/projects/{project["project_id"]}'
            self.assertEqual(422, (await client.patch(path, json={"name": None})).status_code)
            self.assertEqual(422, (await client.patch(path, json={"pinned": None})).status_code)
            updated = await client.patch(path, json={"name": "Renamed", "pinned": True})
            self.assertTrue(updated.json()["pinned"])
            self.assertEqual("Renamed", updated.json()["name"])
            listed = (await client.get("/api/projects")).json()
            self.assertEqual([project["project_id"]], [row["project_id"] for row in listed])
            thread_path = f"/api/chat/thread/{conversation.thread_id}"
            for fields in ({"project_id": foreign.project_id},):
                self.assertEqual(404, (await client.patch(thread_path, json=fields)).status_code)
            for method in (client.patch, client.delete):
                kwargs = {"json": {"name": "Stolen"}} if method == client.patch else {}
                self.assertEqual(404, (await method(f"/api/projects/{foreign.project_id}", **kwargs)).status_code)
            self.assertEqual(404, (await client.get(f"/api/chat/thread?project_id={foreign.project_id}")).status_code)
            self.assertEqual(422, (await client.get("/api/chat/thread?project_id=   ")).status_code)
            bound = await client.patch(thread_path, json={"project_id": project["project_id"], "pinned": True})
            self.assertEqual(project["project_id"], bound.json()["project_id"])
            self.assertTrue(bound.json()["pinned"])
            self.assertEqual([], (await client.get("/api/chat/thread?unassigned=true")).json()["items"])
            self.assertEqual(1, len((await client.get("/api/chat/thread?pinned=true")).json()["items"]))
            self.assertEqual(1, len((await client.get(f'/api/chat/thread?project_id={project["project_id"]}')).json()["items"]))
            # 未传归属字段时保持原值，显式 null 才移出。
            renamed = (await client.patch(thread_path, json={"title": "Updated"})).json()
            self.assertEqual(project["project_id"], renamed["project_id"])
            removed = (await client.patch(thread_path, json={"project_id": None, "pinned": False})).json()
            self.assertIsNone(removed["project_id"])
            self.assertFalse(removed["pinned"])
            await client.patch(thread_path, json={"project_id": project["project_id"]})
            self.assertEqual(204, (await client.delete(path)).status_code)
            self.assertIsNone(conversation.project_id)
            self.assertIsNone(conversation.deleted_at)
            self.assertEqual(404, (await client.patch(thread_path, json={"project_id": project["project_id"]})).status_code)

    async def test_pin_keyset_crosses_ties_and_unpinned_boundary(self):
        now = datetime(2026, 11, 13, tzinfo=UTC)
        rows = [await self.conversation() for _ in range(6)]
        for index, row in enumerate(rows):
            row.updated_at = now + timedelta(minutes=index)
        rows[0].pinned_at = rows[1].pinned_at = now
        rows[2].pinned_at = now + timedelta(minutes=1)
        # 相同置顶和活跃时间仍以 ID 排序。
        rows[0].updated_at = rows[1].updated_at = now
        await self.db.flush()
        expected = [rows[i].id for i in (2, 1, 0, 5, 4, 3)]
        actual = []
        cursor = {}
        while True:
            page = await self.conversations.list_top_level_for_user(uid="user-1", limit=2, **cursor)
            if not page:
                break
            actual.extend(row.id for row, _ in page)
            last, activity = page[-1]
            cursor = {"before_activity_at": activity, "before_id": last.id, "before_pinned_at": last.pinned_at}
        self.assertEqual(expected, actual)
        pinned = await self.conversations.list_top_level_for_user(uid="user-1", limit=10, pinned=True, query="Thread")
        self.assertEqual(expected[:3], [row.id for row, _ in pinned])
        encoded = thread_service._encode_cursor(now, rows[0].id, now)
        self.assertEqual((now, rows[0].id, now), thread_service._decode_cursor(encoded))

    async def test_soft_delete_and_detach_roll_back_together(self):
        project = await self.projects.create("user-1", "Rollback")
        conversation = await self.conversation(project_id=project.project_id)
        self.session.commit()
        await self.projects.soft_delete(project)
        self.assertIsNone(conversation.project_id)
        self.session.rollback()
        self.assertIsNone(project.deleted_at)
        self.assertEqual(project.project_id, conversation.project_id)

    async def test_creation_rejects_foreign_project_before_creating_thread(self):
        project = await self.projects.create("user-2", "Private")
        with patch.object(thread_service, "UserRepository") as users:
            from unittest.mock import AsyncMock
            users.return_value.get_by_uid = AsyncMock(return_value=SimpleNamespace(uid="user-1"))
            with self.assertRaises(LookupError):
                await thread_service.create_thread(self.db, uid="user-1", agent_id="leader", title=None, summary=None, metadata=None, project_id=project.project_id)
        self.assertEqual(0, self.session.query(Conversation).count())


class ProjectMigrationTest(unittest.TestCase):
    def test_upgrade_downgrade_preserves_conversations(self):
        path = Path(__file__).resolve().parents[1] / "migrate/versions/0030_project_and_pinned.py"
        spec = importlib.util.spec_from_file_location("project_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        engine = sa.create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE conversation (id INTEGER PRIMARY KEY, uid VARCHAR(64), deleted_at DATETIME, updated_at DATETIME, title VARCHAR(255))")
            connection.exec_driver_sql("INSERT INTO conversation (id, uid, title) VALUES (1, 'user-1', 'Keep me')")
            with patch.object(migration, "op", Operations(MigrationContext.configure(connection))):
                migration.upgrade()
                self.assertIn("project", sa.inspect(connection).get_table_names())
                fk = sa.inspect(connection).get_foreign_keys("conversation")[0]
                self.assertEqual(["project_id"], fk["referred_columns"])
                self.assertEqual("SET NULL", fk["options"]["ondelete"])
                self.assertEqual((None, None), tuple(connection.exec_driver_sql("SELECT project_id, pinned_at FROM conversation").one()))
                migration.downgrade()
                self.assertNotIn("project", sa.inspect(connection).get_table_names())
                self.assertEqual("Keep me", connection.exec_driver_sql("SELECT title FROM conversation").scalar_one())
