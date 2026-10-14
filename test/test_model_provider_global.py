"""平台 Provider 所有权及历史配置安全迁移。"""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import create_engine, inspect, text

from server.entities.model import ModelProviderCreate
from server.service import model_service as service
from src.configs import config
from src.database.models import ModelProvider, User
from src.database.repositories.model_repository import ModelRepository
from test.test_model_repository import SQLiteModelTestCase


class ModelGlobalProviderTest(SQLiteModelTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await service.create_provider(self.db, ModelProviderCreate(
            provider_id="deepseek", name="Shared", base_url="https://example.com/v1",
            api_key="shared-key", is_enabled=True,
            enabled_models=[{"model_id": "chat", "model_type": "deepseek"}],
        ))

    async def test_repositories_share_global_configuration_and_deletion(self):
        other = ModelRepository(self.db)
        provider = await other.get_provider_by_id("deepseek")
        self.assertEqual(provider.name, "Shared")
        self.assertEqual((await service.resolve_runtime_model(self.db, "deepseek:chat")).api_key.get_secret_value(), "shared-key")
        await service.delete_provider(self.db, "deepseek")
        self.assertIsNone(await other.get_provider_by_id("deepseek"))

    async def test_deleting_user_does_not_delete_or_modify_provider(self):
        self.session.delete(self.session.get(User, 1))
        self.session.commit()
        provider = await self.repository.get_provider_by_id("deepseek")
        self.assertEqual(provider.api_key, "shared-key")
        self.assertEqual(provider.name, "Shared")
        self.assertNotIn("user_id", ModelProvider.__table__.columns)
        self.assertEqual([column.name for column in ModelProvider.__table__.primary_key], ["provider_id"])

    async def test_repository_rejects_identity_and_ownership_changes(self):
        provider = await self.repository.get_provider_by_id("deepseek")
        for values in ({"user_id": 2}, {"provider_id": "other"}):
            with self.assertRaises(ValueError):
                await self.repository.update_provider(provider, **values)


def migration(name):
    path = Path(__file__).resolve().parents[1] / "migrate/versions" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ModelUserMigrationTest(unittest.TestCase):
    def test_empty_scope_upgrade_and_encryption_migration(self):
        old = migration("0008_model_provider.py")
        scoped = migration("0009_model_provider_user.py")
        encrypted = migration("0010_model_credentials_encrypted.py")
        engine = create_engine("sqlite://")
        try:
            User.__table__.create(engine)
            with engine.begin() as db:
                db.execute(User.__table__.insert(), [{"id": i, "uid": f"u{i}", "email": f"u{i}@test", "password_hash": "unused"} for i in (1, 2)])
                operations = Operations(MigrationContext.configure(db))
                with patch.object(old, "op", operations):
                    old.upgrade()
                with patch.object(scoped, "op", operations):
                    scoped.upgrade()
                db.execute(text("INSERT INTO model_provider (user_id,provider_id,name,base_url,protocol,api_key,extra_headers,is_enabled,enabled_models) VALUES (1,'deepseek','old','https://example.com/v1','openai_compatible','old-key','{\"X-Private\":\"header-key\"}',1,'[]')"))
                with patch.object(encrypted, "op", operations), patch.object(config, "model_credential_key", SecretStr("")):
                    with self.assertRaises(RuntimeError):
                        encrypted.upgrade()
                self.assertEqual(db.execute(text("SELECT api_key FROM model_provider")).scalar_one(), "old-key")
                with patch.object(encrypted, "op", operations), patch.object(config, "model_credential_key", SecretStr(Fernet.generate_key().decode())):
                    encrypted.upgrade()
                    row = db.execute(text("SELECT api_key,extra_headers FROM model_provider")).one()
                    self.assertNotIn("old-key", str(row))
                    self.assertNotIn("header-key", str(row))
                    encrypted.downgrade()
                self.assertEqual(db.execute(text("SELECT api_key FROM model_provider")).scalar_one(), "old-key")
                db.execute(text("INSERT INTO model_provider (user_id,provider_id,name,base_url,protocol,api_key,extra_headers,is_enabled,enabled_models) VALUES (2,'deepseek','second','https://example.com/v1','openai_compatible','','{}',1,'[]')"))
                with patch.object(scoped, "op", operations), self.assertRaises(RuntimeError):
                    scoped.downgrade()
                self.assertEqual(db.execute(text("SELECT count(*) FROM model_provider")).scalar_one(), 2)
        finally:
            engine.dispose()

    def test_unassigned_data_is_preserved_and_explicit_mapping_is_required(self):
        old = migration("0008_model_provider.py")
        current = migration("0009_model_provider_user.py")
        engine = create_engine("sqlite://")
        try:
            User.__table__.create(engine)
            with engine.begin() as db:
                db.execute(User.__table__.insert(), [{"id": 1, "uid": "u1", "email": "u1@test", "password_hash": "unused"}])
                operations = Operations(MigrationContext.configure(db))
                with patch.object(old, "op", operations):
                    old.upgrade()
                db.execute(text("INSERT INTO model_provider (provider_id,name,base_url,protocol,api_key,extra_headers,is_enabled,enabled_models) VALUES ('deepseek','old','http://local/v1','openai_compatible','old-key','{}',1,'[]')"))
                with patch.object(current, "op", operations), patch.object(current.context, "get_x_argument", return_value={}):
                    with self.assertRaises(RuntimeError):
                        current.upgrade()
                self.assertNotIn("user_id", {c["name"] for c in inspect(db).get_columns("model_provider")})
                self.assertEqual(db.execute(text("SELECT api_key FROM model_provider")).scalar_one(), "old-key")
                with patch.object(current, "op", operations), patch.object(current.context, "get_x_argument", return_value={"model_provider_owners": '{"deepseek":1}'}):
                    current.upgrade()
                self.assertEqual(inspect(db).get_pk_constraint("model_provider")["constrained_columns"], ["user_id", "provider_id"])
                self.assertFalse(next(c for c in inspect(db).get_columns("model_provider") if c["name"] == "user_id")["nullable"])
                self.assertEqual(db.execute(text("SELECT user_id,api_key FROM model_provider")).one(), (1, "old-key"))
                with patch.object(current, "op", operations):
                    current.downgrade()
                self.assertEqual(db.execute(text("SELECT api_key FROM model_provider")).scalar_one(), "old-key")
        finally:
            engine.dispose()
