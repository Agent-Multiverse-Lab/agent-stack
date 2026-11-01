"""在独立 PostgreSQL schema 中验证 Run 来源字段迁移，事务结束后回滚。"""

import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from src.configs import config


@unittest.skipUnless(os.environ.get("RUN_MIGRATION_TEST") == "1", "设置 RUN_MIGRATION_TEST=1 执行 PostgreSQL 迁移回归")
class RunCreatedByMigrationTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(config.database_url)
        self.addAsyncCleanup(self.engine.dispose)
        self.connection = await self.engine.connect()
        self.addAsyncCleanup(self.connection.close)
        transaction = await self.connection.begin()
        self.addAsyncCleanup(transaction.rollback)
        schema = f"test_run_created_by_{uuid4().hex}"
        await self.connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        await self.connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        path = Path(__file__).resolve().parents[1] / "migrate/versions/0024_run_created_by.py"
        spec = importlib.util.spec_from_file_location("run_created_by_migration", path)
        self.migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.migration)

    def run_case(self, connection, bootstrap):
        column = "created_by_run_id" if bootstrap else "parent_run_id"
        connection.execute(text(f"CREATE TABLE agent_run (id VARCHAR(64) PRIMARY KEY, {column} VARCHAR(64), run_type VARCHAR(32) NOT NULL)"))
        connection.execute(text(f"CREATE INDEX ix_agent_run_{column} ON agent_run ({column})"))
        connection.execute(text(f"""
            INSERT INTO agent_run (id, {column}, run_type)
            VALUES ('main', NULL, 'chat'), ('child', 'main', 'subagent'), ('resume', 'main', 'resume')
        """))
        before = connection.execute(text(f"SELECT id, {column}, run_type FROM agent_run ORDER BY id")).all()
        operations = Operations(MigrationContext.configure(connection))
        with patch.object(self.migration, "op", operations):
            self.migration.upgrade()

        inspector = inspect(connection)
        self.assertEqual({"id", "created_by_run_id", "run_type"}, {item["name"] for item in inspector.get_columns("agent_run")})
        self.assertEqual({"ix_agent_run_created_by_run_id"}, {item["name"] for item in inspector.get_indexes("agent_run")})
        self.assertEqual(before, connection.execute(text("SELECT id, created_by_run_id, run_type FROM agent_run ORDER BY id")).all())

        with patch.object(self.migration, "op", operations):
            self.migration.downgrade()
        inspector = inspect(connection)
        self.assertEqual({"id", "parent_run_id", "run_type"}, {item["name"] for item in inspector.get_columns("agent_run")})
        self.assertEqual({"ix_agent_run_parent_run_id"}, {item["name"] for item in inspector.get_indexes("agent_run")})
        self.assertEqual(before, connection.execute(text("SELECT id, parent_run_id, run_type FROM agent_run ORDER BY id")).all())

    async def test_rename_preserves_chat_subagent_and_resume_relationships(self):
        await self.connection.run_sync(self.run_case, False)

    async def test_current_orm_bootstrap_can_be_upgraded_and_downgraded(self):
        await self.connection.run_sync(self.run_case, True)
