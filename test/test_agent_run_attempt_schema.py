"""执行尝试的结构、外键及迁移验证；不测试尚未接入的运行流程。"""

import importlib.util
import io
import os
import unittest
import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import configure_mappers

from src.database import AgentRunAttempt
from src.database.base import Base
from src.database.models import AgentRun, Conversation, Message, User

POSTGRES_URL = os.environ.get("AGENT_STACK_SCHEMA_TEST_POSTGRES_URL")
MIGRATION_PATH = (
    Path(__file__).resolve().parents[1] / "migrate/versions/0017_agent_run_attempt.py"
)
spec = importlib.util.spec_from_file_location("agent_run_attempt_migration", MIGRATION_PATH)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class DatabaseTestCase(unittest.TestCase):
    database_url = "sqlite://"
    foreign_keys = True

    def setUp(self):
        self.engine = sa.create_engine(self.database_url)
        self.db = self.engine.connect()
        self.transaction = self.db.begin()
        if self.db.dialect.name == "postgresql":
            # 每个测试的表都在一次可回滚事务的独立 schema 中，绝不修改业务表。
            schema = "attempt_test_" + uuid.uuid4().hex
            self.db.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            self.db.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
        elif self.foreign_keys:
            self.db.exec_driver_sql("PRAGMA foreign_keys=ON")

    def tearDown(self):
        self.transaction.rollback()
        self.db.close()
        self.engine.dispose()

    def assert_integrity_error(self, statement):
        with self.assertRaises(IntegrityError), self.db.begin_nested():
            self.db.execute(statement)


class RunAttemptSchemaTest(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        configure_mappers()
        Base.metadata.create_all(self.db, tables=[
            User.__table__, Conversation.__table__, Message.__table__,
            AgentRun.__table__, AgentRunAttempt.__table__,
        ])
        self.run = AgentRun.__table__
        self.attempt = AgentRunAttempt.__table__
        self.db.execute(User.__table__.insert().values(
            uid="user-1", email="user@example.test", password_hash="unused",
        ))
        self.db.execute(Conversation.__table__.insert().values(
            id=1, uid="user-1", thread_id="thread-1", agent_id="agent", title="test",
        ))
        self.db.execute(self.run.insert(), [
            {"id": run_id, "uid": "user-1", "conversation_id": 1,
             "thread_id": "thread-1", "agent_id": "agent", "agent_status": "running"}
            for run_id in ("run-1", "run-2")
        ])

    def insert_attempt(self, attempt_id="attempt-1", run_id="run-1", attempt_no=1, **changes):
        self.db.execute(self.attempt.insert().values(
            id=attempt_id, run_id=run_id, attempt_no=attempt_no, worker_id="worker-1", status="running", **changes,
        ))

    def test_old_run_insert_leaves_worker_null_and_no_history(self):
        self.assertNotIn("current_attempt_id", self.run.c)
        self.assertNotIn("owner_worker_id", self.run.c)
        self.assertEqual(self.db.execute(sa.select(self.run.c.worker_id)).all(), [(None,), (None,)])
        self.assertEqual(self.db.scalar(sa.select(sa.func.count()).select_from(self.attempt)), 0)

    def test_attempt_numbers_are_unique_within_each_run(self):
        self.insert_attempt()
        self.assert_integrity_error(self.attempt.insert().values(
            id="duplicate", run_id="run-1", attempt_no=1, worker_id="worker-1", status="running",
        ))
        # 同一 Run 只允许一条开放 attempt；先结束第一条，再创建下一条。
        self.db.execute(self.attempt.update().where(
            self.attempt.c.id == "attempt-1"
        ).values(finished_at=datetime.now(UTC), status="completed"))
        self.insert_attempt("attempt-2", attempt_no=2)
        self.insert_attempt("attempt-3", run_id="run-2")
        rows = self.db.execute(sa.select(self.attempt).order_by(self.attempt.c.id)).mappings().all()
        self.assertEqual([row["attempt_no"] for row in rows], [1, 2, 1])
        self.assertEqual({row["worker_id"] for row in rows}, {"worker-1"})
        self.assertTrue(all(row["started_at"] is not None for row in rows))

    def test_only_one_open_attempt_per_run(self):
        self.insert_attempt()
        self.assert_integrity_error(self.attempt.insert().values(
            id="second-open", run_id="run-1", attempt_no=2,
            worker_id="worker-2", status="running",
        ))

    def test_attempt_requires_existing_run_and_required_fields(self):
        self.assert_integrity_error(self.attempt.insert().values(
            id="orphan", run_id="missing", attempt_no=1, worker_id="worker-1", status="running",
        ))
        for field in ("run_id", "attempt_no", "worker_id", "status", "started_at"):
            values = dict(id="invalid", run_id="run-1", attempt_no=1, worker_id="worker-1", status="running")
            values[field] = None
            with self.subTest(field=field):
                self.assert_integrity_error(self.attempt.insert().values(**values))

    def test_attempt_can_be_deleted_without_updating_run(self):
        self.insert_attempt()
        self.db.execute(self.attempt.delete().where(self.attempt.c.id == "attempt-1"))
        self.assertEqual(self.db.scalar(sa.select(sa.func.count()).select_from(self.run)), 2)

    def test_run_delete_cascades_own_history(self):
        self.insert_attempt()
        self.insert_attempt("attempt-2", "run-2")
        self.db.execute(self.run.delete().where(self.run.c.id == "run-1"))
        self.assertEqual(self.db.execute(sa.select(self.attempt.c.id)).scalars().all(), ["attempt-2"])
        self.db.execute(Conversation.__table__.delete().where(Conversation.__table__.c.id == 1))
        self.assertEqual(self.db.scalar(sa.select(sa.func.count()).select_from(self.attempt)), 0)


@unittest.skipUnless(POSTGRES_URL, "未配置独立 PostgreSQL 结构测试数据库")
class PostgresRunAttemptSchemaTest(RunAttemptSchemaTest):
    database_url = POSTGRES_URL


class RunAttemptMigrationTest(DatabaseTestCase):
    # SQLite batch ALTER 重建表；迁移结构比较使用默认的 FK OFF，完整外键行为见上方测试。
    foreign_keys = False

    def setUp(self):
        super().setUp()
        self.legacy = sa.Table(
            "agent_run", sa.MetaData(),
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("agent_status", sa.String(32), nullable=False),
            sa.Column("request_id", sa.String(128), unique=True),
            sa.Column("error", sa.Text()),
            sa.Column("run_metadata", sa.JSON(), nullable=False),
            sa.Index("ix_legacy_status", "agent_status"),
        )
        self.legacy.create(self.db)
        self.rows = [
            {"id": f"run-{i}", "agent_status": status, "request_id": f"request-{i}",
             "error": "existing error" if status == "failed" else None,
             "run_metadata": {"model": "existing-model", "value": i}}
            for i, status in enumerate((
                "pending", "queued", "running", "cancel_requested",
                "completed", "failed", "cancelled", "interrupted",
            ))
        ]
        self.db.execute(self.legacy.insert(), self.rows)
        self.operations = Operations(MigrationContext.configure(self.db))

    def migrate(self, direction="upgrade"):
        with patch.object(migration, "op", self.operations):
            getattr(migration, direction)()

    def assert_legacy_unchanged(self):
        self.assertEqual(
            self.db.execute(sa.select(self.legacy).order_by(self.legacy.c.id)).mappings().all(),
            self.rows,
        )
        inspector = sa.inspect(self.db)
        self.assertIn("ix_legacy_status", {item["name"] for item in inspector.get_indexes("agent_run")})
        self.assertIn(["request_id"], [item["column_names"] for item in inspector.get_unique_constraints("agent_run")])

    def test_upgrade_preserves_rows_and_matches_attempt_model(self):
        self.migrate()
        self.assert_legacy_unchanged()
        inspector = sa.inspect(self.db)
        columns = {item["name"]: item for item in inspector.get_columns("agent_run_attempt")}
        self.assertEqual(
            set(columns),
            set(AgentRunAttempt.__table__.c.keys())
            - {"attempt_no", "heartbeat_at", "lease_expires_at"},
        )
        for column in AgentRunAttempt.__table__.c:
            if column.name in {"attempt_no", "heartbeat_at", "lease_expires_at"}:
                continue
            with self.subTest(column=column.name):
                self.assertEqual(columns[column.name]["nullable"], column.nullable)
                self.assertEqual(
                    str(columns[column.name]["type"].compile(dialect=self.db.dialect)),
                    str(column.type.compile(dialect=self.db.dialect)),
                )
        self.assertIsNotNone(columns["started_at"]["default"])
        current_fk = next(
            item for item in inspector.get_foreign_keys("agent_run")
            if item["name"] == "fk_agent_run_current_attempt"
        )
        self.assertEqual(current_fk["constrained_columns"], ["id", "current_attempt_id"])
        self.assertEqual(current_fk["referred_columns"], ["run_id", "id"])
        self.assertEqual(current_fk["referred_table"], "agent_run_attempt")
        attempt_fk = inspector.get_foreign_keys("agent_run_attempt")[0]
        self.assertEqual(attempt_fk["options"].get("ondelete"), "CASCADE")
        self.assertIn(["run_id", "id"], [
            item["column_names"] for item in inspector.get_unique_constraints("agent_run_attempt")
        ])
        indexes = {item["name"]: item for item in inspector.get_indexes("agent_run_attempt")}
        self.assertEqual(indexes["ix_agent_run_attempt_run_started"]["column_names"], ["run_id", "started_at"])
        rows = self.db.execute(sa.text("SELECT current_attempt_id, owner_worker_id FROM agent_run")).all()
        self.assertEqual(rows, [(None, None)] * len(self.rows))
        self.assertEqual(self.db.scalar(sa.text("SELECT COUNT(*) FROM agent_run_attempt")), 0)

    def test_downgrade_with_current_attempt_preserves_legacy_data(self):
        self.migrate()
        self.db.execute(AgentRunAttempt.__table__.insert().values(
            id="attempt-1", run_id="run-0", worker_id="worker-1", status="running",
        ))
        self.db.execute(sa.text(
            "UPDATE agent_run SET current_attempt_id='attempt-1', owner_worker_id='worker-1' "
            "WHERE id='run-0'"
        ))
        self.migrate("downgrade")
        self.assert_legacy_unchanged()
        inspector = sa.inspect(self.db)
        self.assertNotIn("agent_run_attempt", inspector.get_table_names())
        self.assertEqual({c["name"] for c in inspector.get_columns("agent_run")}, set(self.legacy.c.keys()))
        self.migrate()
        self.assert_legacy_unchanged()

    def test_existing_style_insert_still_works_after_upgrade(self):
        self.migrate()
        self.db.execute(self.legacy.insert().values(
            id="new-run", agent_status="pending", request_id="new-request", run_metadata={},
        ))
        self.assertEqual(self.db.execute(sa.text(
            "SELECT current_attempt_id, owner_worker_id FROM agent_run WHERE id='new-run'"
        )).one(), (None, None))


@unittest.skipUnless(POSTGRES_URL, "未配置独立 PostgreSQL 结构测试数据库")
class PostgresRunAttemptMigrationTest(RunAttemptMigrationTest):
    database_url = POSTGRES_URL


class RunAttemptPostgresDDLTest(unittest.TestCase):
    def test_offline_upgrade_and_downgrade_break_fk_cycle_in_order(self):
        buffer = io.StringIO()
        operations = Operations(MigrationContext.configure(
            dialect_name="postgresql", opts={"as_sql": True, "output_buffer": buffer},
        ))
        with patch.object(migration, "op", operations):
            migration.upgrade()
            migration.downgrade()
        sql = buffer.getvalue()
        self.assertLess(sql.index("CREATE TABLE agent_run_attempt"), sql.index("ADD CONSTRAINT fk_agent_run_current_attempt"))
        self.assertLess(sql.index("DROP CONSTRAINT fk_agent_run_current_attempt"), sql.index("DROP TABLE agent_run_attempt"))
        self.assertIn("TIMESTAMP WITH TIME ZONE", sql)
        self.assertNotIn("UPDATE ", sql)
        self.assertNotIn("INSERT INTO ", sql)
        self.assertEqual(migration.down_revision, "0016_qwen_provider_id")


number_spec = importlib.util.spec_from_file_location(
    "agent_run_attempt_no_migration", MIGRATION_PATH.with_name("0018_agent_run_attempt_no.py"),
)
number_migration = importlib.util.module_from_spec(number_spec)
number_spec.loader.exec_module(number_migration)


class RunAttemptNumberPostgresDDLTest(unittest.TestCase):
    def test_upgrade_and_downgrade_order(self):
        buffer = io.StringIO()
        operations = Operations(MigrationContext.configure(
            dialect_name="postgresql", opts={"as_sql": True, "output_buffer": buffer},
        ))
        with patch.object(number_migration, "op", operations):
            number_migration.upgrade()
            number_migration.downgrade()
        sql = buffer.getvalue()
        self.assertLess(sql.index("DROP CONSTRAINT fk_agent_run_current_attempt"),
                        sql.index("DROP CONSTRAINT uq_agent_run_attempt_run_id_id"))
        self.assertLess(sql.index("UPDATE agent_run_attempt"),
                        sql.index("ALTER COLUMN attempt_no SET NOT NULL"))
        self.assertLess(sql.index("ADD CONSTRAINT uq_agent_run_attempt_run_id_id"),
                        sql.index("ADD CONSTRAINT fk_agent_run_current_attempt"))
        self.assertIn("UNIQUE (run_id, attempt_no)", sql)


class RunAttemptNumberMigrationTest(RunAttemptMigrationTest):
    def migrate_number(self, direction="upgrade"):
        with patch.object(number_migration, "op", self.operations):
            getattr(number_migration, direction)()

    def test_number_backfill_and_roundtrip_preserve_history(self):
        self.migrate()
        self.db.execute(sa.text("""
            INSERT INTO agent_run_attempt (id, run_id, worker_id, status, started_at)
            VALUES ('b', 'run-0', 'worker-1', 'completed', '2026-01-01 00:00:00'),
                   ('a', 'run-0', 'worker-1', 'failed', '2026-01-01 00:00:00'),
                   ('c', 'run-1', 'worker-2', 'running', '2026-01-02 00:00:00')
        """))
        self.db.execute(sa.text("UPDATE agent_run SET current_attempt_id='b', owner_worker_id='worker-1' WHERE id='run-0'"))
        self.migrate_number()
        self.assert_legacy_unchanged()
        inspector = sa.inspect(self.db)
        self.assertNotIn("current_attempt_id", {c["name"] for c in inspector.get_columns("agent_run")})
        self.assertNotIn("owner_worker_id", {c["name"] for c in inspector.get_columns("agent_run")})
        self.assertEqual(self.db.scalar(sa.text("SELECT worker_id FROM agent_run WHERE id='run-0'")), "worker-1")
        self.assertEqual(self.db.execute(sa.text(
            "SELECT id, worker_id FROM agent_run_attempt ORDER BY id"
        )).all(), [("a", "worker-1"), ("b", "worker-1"), ("c", "worker-2")])
        self.assertFalse(any(fk["referred_table"] == "agent_run_attempt"
                             for fk in inspector.get_foreign_keys("agent_run")))
        self.assertEqual(self.db.execute(sa.text(
            "SELECT id, attempt_no FROM agent_run_attempt ORDER BY id"
        )).all(), [("a", 1), ("b", 2), ("c", 1)])
        uniques = [c["column_names"] for c in inspector.get_unique_constraints("agent_run_attempt")]
        self.assertIn(["run_id", "attempt_no"], uniques)
        self.assertNotIn(["run_id", "id"], uniques)
        self.assertFalse(next(c for c in inspector.get_columns("agent_run_attempt")
                              if c["name"] == "attempt_no")["nullable"])
        self.migrate_number("downgrade")
        self.assertEqual(self.db.scalar(sa.text("SELECT COUNT(*) FROM agent_run_attempt")), 3)
        self.assertIsNone(self.db.scalar(sa.text("SELECT current_attempt_id FROM agent_run WHERE id='run-0'")))
        self.assertEqual(self.db.scalar(sa.text("SELECT owner_worker_id FROM agent_run WHERE id='run-0'")), "worker-1")
        self.migrate_number()
        self.assert_legacy_unchanged()

    def test_empty_upgrade(self):
        self.migrate()
        self.migrate_number()
        self.assert_legacy_unchanged()
        self.assertEqual(self.db.scalar(sa.text("SELECT COUNT(*) FROM agent_run_attempt")), 0)


@unittest.skipUnless(POSTGRES_URL, "未配置独立 PostgreSQL 结构测试数据库")
class PostgresRunAttemptNumberMigrationTest(RunAttemptNumberMigrationTest):
    database_url = POSTGRES_URL


if __name__ == "__main__":
    unittest.main()
