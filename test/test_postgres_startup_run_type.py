"""启动只补表结构，不按 Agent 身份重写 Run 的执行类型。

使用 SQLite 执行数据 SQL，仅适配 ADD COLUMN IF NOT EXISTS；不替代真实
PostgreSQL 的 DDL/并发集成验证。生产 create_all 在此由最小测试表替代。
"""

import sqlite3
import unittest
from contextlib import asynccontextmanager
from unittest.mock import Mock, patch

from src.database.manger import Base, PostgreManger


class _SQLiteStartupConnection:
    def __init__(self, db):
        self.db = db
        self.statements = []

    async def run_sync(self, callback):
        return callback(self.db)

    async def execute(self, statement):
        sql = str(statement)
        self.statements.append(sql)
        if sql.startswith("ALTER TABLE agent_run ADD COLUMN IF NOT EXISTS"):
            columns = {row[1] for row in self.db.execute("PRAGMA table_info(agent_run)")}
            if "run_type" in columns:
                return
            sql = sql.replace("ADD COLUMN IF NOT EXISTS", "ADD COLUMN")
        return self.db.execute(sql)


class PostgresStartupRunTypeTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.execute("CREATE TABLE agent (slug TEXT PRIMARY KEY, role TEXT)")
        self.db.executemany(
            "INSERT INTO agent VALUES (?, ?)",
            [("leader", "leader"), ("child", "subagent")],
        )
        self.connection = _SQLiteStartupConnection(self.db)

        @asynccontextmanager
        async def begin():
            with self.db:
                yield self.connection

        self.manager = PostgreManger()
        self.manager.engine = Mock(begin=begin)
        self.manager.initialized = True
        create_all_patch = patch.object(Base.metadata, "create_all")
        self.create_all = create_all_patch.start()
        self.addCleanup(create_all_patch.stop)

    async def test_repeated_startup_preserves_run_types_and_lifecycle_states(self):
        self.db.execute(
            "CREATE TABLE agent_run (id INTEGER PRIMARY KEY, agent_id TEXT, "
            "run_type VARCHAR(32) NOT NULL DEFAULT 'chat', agent_status TEXT)"
        )
        rows = [
            (i, agent, run_type, status)
            for i, (agent, run_type, status) in enumerate(
                (agent, run_type, status)
                for agent in ("leader", "child")
                for run_type in ("chat", "subagent", "resume")
                for status in ("pending", "queued", "running", "cancel_requested", "completed", "failed", "cancelled", "interrupted")
            )
        ]
        self.db.executemany("INSERT INTO agent_run VALUES (?, ?, ?, ?)", rows)
        for _ in range(3):
            await self.manager.ensure_tables_exist()
            self.assertEqual(self.db.execute("SELECT * FROM agent_run ORDER BY id").fetchall(), rows)
        # Agent 的角色后来变化，也不应追溯重写已有 Run。
        self.db.execute("UPDATE agent SET role = 'subagent' WHERE slug = 'leader'")
        self.db.execute("UPDATE agent SET role = 'leader' WHERE slug = 'child'")
        await self.manager.create_tables()
        self.assertEqual(self.db.execute("SELECT * FROM agent_run ORDER BY id").fetchall(), rows)
        self.assertEqual(self.create_all.call_count, 4)
        for call in self.create_all.call_args_list:
            self.assertEqual(call.kwargs, {"bind": self.db, "checkfirst": True})
        self.assertFalse(any(sql.lstrip().upper().startswith("UPDATE ") for sql in self.connection.statements))

    async def test_legacy_schema_still_gets_column_and_index_idempotently(self):
        self.db.execute("CREATE TABLE agent_run (id INTEGER PRIMARY KEY, agent_id TEXT, agent_status TEXT)")
        self.db.execute("INSERT INTO agent_run VALUES (1, 'leader', 'completed')")
        for _ in range(2):
            await self.manager.ensure_tables_exist()
        self.assertEqual(
            self.db.execute("SELECT id, agent_id, agent_status, run_type FROM agent_run").fetchall(),
            [(1, "leader", "completed", "chat")],
        )
        index_names = {row[1] for row in self.db.execute("PRAGMA index_list(agent_run)")}
        self.assertIn("ix_agent_run_run_type", index_names)

    async def test_empty_database_still_invokes_create_all(self):
        def create_all(*, bind, checkfirst):
            self.assertTrue(checkfirst)
            bind.execute("CREATE TABLE IF NOT EXISTS agent_run (id INTEGER PRIMARY KEY, agent_id TEXT)")

        self.create_all.side_effect = create_all
        await self.manager.ensure_tables_exist()
        self.assertEqual(self.db.execute("SELECT count(*) FROM agent_run").fetchone()[0], 0)
        self.assertIn("run_type", {row[1] for row in self.db.execute("PRAGMA table_info(agent_run)")})

    async def test_uninitialized_manager_does_not_execute_sql(self):
        self.manager.initialized = False
        with self.assertRaisesRegex(RuntimeError, "not initialized"):
            await self.manager.ensure_tables_exist()
        self.assertEqual(self.connection.statements, [])
        self.create_all.assert_not_called()


if __name__ == "__main__":
    unittest.main()
