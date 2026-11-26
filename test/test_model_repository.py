"""用真实 SQLite 事务验证仓储；异步 Session 方法桥接至同步测试 Session。"""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.database.models import ModelProvider, User
from src.model.repository import ModelProviderRepository


class SQLiteModelTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
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
        self.repository = ModelProviderRepository(self.db)

    async def asyncTearDown(self):
        self.session.close()
        self.engine.dispose()

    async def insert_provider(self, provider_id="local", **values):
        return await self.repository.create_model_provider(
            **{
                "provider_id": provider_id,
                "name": "Local",
                "base_url": "http://localhost:11434/v1",
                "protocol": "openai_compatible",
                "api_key": "secret-key",
                "extra_headers": {},
                "is_enabled": True,
                "enabled_models": [{"model_id": "qwen3:8b", "category": "chat", "capabilities": []}],
                **values,
            }
        )


class ModelProviderRepositoryTest(SQLiteModelTestCase):
    async def test_crud_persists_replaced_json_and_filters_enabled(self):
        await self.insert_provider()
        await self.insert_provider("disabled", is_enabled=False)
        self.db.commit.assert_not_called()
        await self.db.commit()
        self.assertEqual(["disabled", "local"], [p.provider_id for p in await self.repository.list_model_providers()])
        self.assertEqual(["local"], [p.provider_id for p in await self.repository.list_model_providers(enabled_only=True)])
        fetched = await self.repository.get_model_provider_by_id("local")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "Local")
        replacement = [{"model_id": "org/new-model", "category": "chat", "capabilities": []}]
        updated = await self.repository.update_model_provider("local", enabled_models=replacement)
        self.assertIsNotNone(updated)
        self.assertIsNone(await self.repository.update_model_provider("missing", name="Nope"))
        await self.db.commit()
        with Session(self.engine) as verifier:
            saved = verifier.get(ModelProvider, "local")
            self.assertEqual(saved.enabled_models, replacement)
            self.assertIsNotNone(saved.created_at)
        self.assertTrue(await self.repository.delete_model_provider("local"))
        self.assertFalse(await self.repository.delete_model_provider("missing"))
        await self.db.commit()
        self.assertIsNone(await self.repository.get_model_provider_by_id("local"))
        self.assertEqual(1, len(await self.repository.list_model_providers()))

    async def test_require_model_validates_format_existence_enabled_and_category(self):
        await self.insert_provider(
            "local",
            enabled_models=[
                {"model_id": "org/qwen3:8b", "category": "chat", "capabilities": []},
                {"model_id": "bge-m3", "category": "embedding", "capabilities": []},
            ],
        )
        await self.insert_provider(
            "disabled",
            is_enabled=False,
            enabled_models=[{"model_id": "m1", "category": "chat", "capabilities": []}],
        )
        await self.db.commit()

        provider, model = await self.repository.require_model("local:org/qwen3:8b", category="chat")
        self.assertEqual(provider.provider_id, "local")
        self.assertEqual(model["model_id"], "org/qwen3:8b")

        _, emb = await self.repository.require_model("local:bge-m3", category="embedding")
        self.assertEqual(emb["category"], "embedding")

        for invalid in ("local", ":model", "local:", "local/model", " local:m", 123):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                await self.repository.require_model(invalid)  # type: ignore[arg-type]

        for missing in ("unknown:model", "local:missing"):
            with self.subTest(missing=missing), self.assertRaises(LookupError):
                await self.repository.require_model(missing)

        with self.assertRaisesRegex(ValueError, "停用"):
            await self.repository.require_model("disabled:m1")
        disabled_provider, _ = await self.repository.require_model("disabled:m1", require_enabled=False)
        self.assertEqual(disabled_provider.provider_id, "disabled")

        with self.assertRaisesRegex(ValueError, "模型类型不匹配"):
            await self.repository.require_model("local:bge-m3", category="chat")

    async def test_duplicate_provider_is_rejected_by_database(self):
        await self.insert_provider()
        await self.db.commit()
        with self.assertRaises(IntegrityError):
            await self.insert_provider()
        await self.db.rollback()
        self.assertEqual(1, len(await self.repository.list_model_providers()))

    async def test_rollback_discards_insert_and_get_refreshes_identity_map(self):
        await self.insert_provider("discard")
        await self.db.rollback()
        self.assertIsNone(await self.repository.get_model_provider_by_id("discard"))
        original = await self.insert_provider()
        await self.db.commit()
        with Session(self.engine) as writer:
            saved = writer.scalar(select(ModelProvider).where(ModelProvider.provider_id == "local"))
            saved.is_enabled = False
            writer.commit()
        refreshed = await self.repository.get_model_provider_by_id("local")
        self.assertIs(original, refreshed)
        self.assertFalse(refreshed.is_enabled)


class ModelMigrationTest(unittest.TestCase):
    def test_upgrade_matches_metadata_and_downgrade_removes_only_new_table(self):
        root = Path(__file__).resolve().parents[1] / "migrate/versions"
        spec_0008 = importlib.util.spec_from_file_location("model_provider_migration", root / "0008_model_provider.py")
        migration = importlib.util.module_from_spec(spec_0008)
        spec_0008.loader.exec_module(migration)
        spec_0032 = importlib.util.spec_from_file_location("model_provider_urls", root / "0032_model_provider_category_urls.py")
        urls_migration = importlib.util.module_from_spec(spec_0032)
        spec_0032.loader.exec_module(urls_migration)
        engine = create_engine("sqlite://")
        try:
            with engine.begin() as connection:
                operations = Operations(MigrationContext.configure(connection))
                with patch.object(migration, "op", operations), patch.object(urls_migration, "op", operations):
                    migration.upgrade()
                    urls_migration.upgrade()
                    actual = {c["name"]: c for c in inspect(connection).get_columns("model_provider")}
                    expected = {column.name: column for column in ModelProvider.__table__.columns if column.name != "user_id"}
                    self.assertEqual(set(actual), set(expected.keys()))
                    for column in expected.values():
                        self.assertEqual(actual[column.name]["nullable"], column.nullable)
                    self.assertEqual(inspect(connection).get_pk_constraint("model_provider")["constrained_columns"], ["provider_id"])
                    urls_migration.downgrade()
                    migration.downgrade()
                    self.assertFalse(inspect(connection).has_table("model_provider"))
        finally:
            engine.dispose()
