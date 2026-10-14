"""用真实 SQLite 事务验证仓储；异步 Session 方法桥接至同步测试 Session。"""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.configs import config
from src.database.models import ModelProvider, User
from src.database.repositories.model_repository import ModelRepository


class SQLiteModelTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        cipher_patch = patch.object(config, "model_credential_key", SecretStr(Fernet.generate_key().decode()))
        cipher_patch.start()
        self.addCleanup(cipher_patch.stop)
        self.engine = create_engine("sqlite://")
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        User.__table__.create(self.engine)
        ModelProvider.__table__.create(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)
        self.user_id = 1
        self.session.add_all([User(id=i, uid=f"u{i}", email=f"u{i}@test.local", password_hash="unused") for i in (1, 2)])
        self.session.commit()
        self.db = AsyncMock(spec=AsyncSession)
        self.db.add.side_effect = self.session.add
        for name in ("execute", "flush", "commit", "rollback", "delete"):
            getattr(self.db, name).side_effect = getattr(self.session, name)
        self.repository = ModelRepository(self.db)

    async def asyncTearDown(self):
        self.session.close()
        self.engine.dispose()

    async def insert_provider(self, provider_id="local", **values):
        return await self.repository.create_provider(
            **{
                "provider_id": provider_id,
                "name": "Local",
                "base_url": "http://localhost:11434/v1",
                "protocol": "openai_compatible",
                "api_key": "secret-key",
                "extra_headers": {},
                "is_enabled": True,
                "enabled_models": [{"model_id": "qwen3:8b", "model_type": "ollama", "body_overrides": {}}],
                **values,
            }
        )


class ModelRepositoryTest(SQLiteModelTestCase):
    async def test_crud_persists_replaced_json_and_filters_enabled(self):
        first = await self.insert_provider()
        await self.insert_provider("disabled", is_enabled=False)
        self.db.commit.assert_not_called()
        await self.db.commit()
        self.assertEqual(["local"], [p.provider_id for p in await self.repository.list_providers(enabled_only=True)])
        replacement = [{"model_id": "org/new-model", "model_type": "qwen", "body_overrides": {"temperature": 0.2}}]
        await self.repository.update_provider(first, enabled_models=replacement)
        await self.db.commit()
        with Session(self.engine) as verifier:
            saved = verifier.get(ModelProvider, "local")
            self.assertEqual(saved.enabled_models, replacement)
            self.assertIsNotNone(saved.created_at)
        await self.repository.delete_provider(first)
        await self.db.commit()
        self.assertIsNone(await self.repository.get_provider_by_id("local"))
        self.assertEqual(1, len(await self.repository.list_providers()))

    async def test_duplicate_provider_is_rejected_by_database(self):
        await self.insert_provider()
        await self.db.commit()
        with self.assertRaises(IntegrityError):
            await self.insert_provider()
        await self.db.rollback()
        self.assertEqual(1, len(await self.repository.list_providers()))

    async def test_rollback_discards_insert_and_get_refreshes_identity_map(self):
        await self.insert_provider("discard")
        await self.db.rollback()
        self.assertIsNone(await self.repository.get_provider_by_id("discard"))
        original = await self.insert_provider()
        await self.db.commit()
        with Session(self.engine) as writer:
            saved = writer.scalar(select(ModelProvider).where(ModelProvider.provider_id == "local"))
            saved.is_enabled = False
            writer.commit()
        refreshed = await self.repository.get_provider_by_id("local")
        self.assertIs(original, refreshed)
        self.assertFalse(refreshed.is_enabled)


class ModelMigrationTest(unittest.TestCase):
    def test_upgrade_matches_metadata_and_downgrade_removes_only_new_table(self):
        path = Path(__file__).resolve().parents[1] / "migrate/versions/0008_model_provider.py"
        spec = importlib.util.spec_from_file_location("model_provider_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        engine = create_engine("sqlite://")
        try:
            with engine.begin() as connection:
                with patch.object(migration, "op", Operations(MigrationContext.configure(connection))):
                    migration.upgrade()
                    actual = {c["name"]: c for c in inspect(connection).get_columns("model_provider")}
                    expected = {column.name: column for column in ModelProvider.__table__.columns if column.name != "user_id"}
                    self.assertEqual(set(actual), set(expected.keys()))
                    for column in expected.values():
                        self.assertEqual(actual[column.name]["nullable"], column.nullable)
                    self.assertEqual(inspect(connection).get_pk_constraint("model_provider")["constrained_columns"], ["provider_id"])
                    migration.downgrade()
                    self.assertFalse(inspect(connection).has_table("model_provider"))
        finally:
            engine.dispose()
