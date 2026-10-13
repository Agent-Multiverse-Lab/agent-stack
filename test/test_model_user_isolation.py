"""两用户同名供应商隔离及旧配置安全迁移。"""

import importlib.util
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from alembic.migration import MigrationContext
from alembic.operations import Operations
from cryptography.fernet import Fernet
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import create_engine, inspect, text

from server.entities.model import ModelProviderCreate
from server.router.model_router import router
from server.service import model_service as service
from server.utils.auth import get_current_user
from src.configs import config
from src.database import get_db
from src.database.models import User
from src.database.repositories.model_repository import ModelRepository
from src.model import model_cache
from test.test_model_repository import SQLiteModelTestCase
from test.test_model_service import FakeRedis


class ModelUserIsolationTest(SQLiteModelTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.redis = FakeRedis()
        self.cache_patch = patch.object(model_cache, "get_async_redis_client", return_value=self.redis)
        self.cache_patch.start()
        self.addCleanup(self.cache_patch.stop)
        for uid in (1, 2):
            await service.create_provider(
                self.db,
                uid,
                ModelProviderCreate(
                    provider_id="deepseek",
                    name=f"private-{uid}",
                    base_url=f"http://user{uid}.local/v1",
                    api_key=f"key-{uid}",
                    extra_headers={"X-Owner": str(uid)},
                    enabled_models=[{"model_id": f"chat-{uid}", "model_type": "deepseek"}],
                ),
            )

    async def test_cache_runtime_and_delete_are_user_scoped(self):
        for uid in (1, 2):
            self.assertEqual([p.name for p in await service.list_providers(self.db, uid)], [f"private-{uid}"])
            self.assertEqual((await service.list_enabled_models(self.db, uid))[0].model_id, f"chat-{uid}")
            connection = await service.resolve_runtime_model(self.db, uid, f"deepseek:chat-{uid}")
            self.assertEqual(connection.api_key.get_secret_value(), f"key-{uid}")
            with self.assertRaises(LookupError):
                await service.resolve_runtime_model(self.db, uid, f"deepseek:chat-{3 - uid}")
        self.assertEqual(set(self.redis.data), {"model:providers:v2:user:1", "model:providers:v2:user:2"})
        other_cache = self.redis.data["model:providers:v2:user:2"]
        await service.delete_provider(self.db, 1, "deepseek")
        self.assertEqual(self.redis.data["model:providers:v2:user:2"], other_cache)
        self.assertEqual((await service.get_provider(self.db, 2, "deepseek")).name, "private-2")
        with self.assertRaises(LookupError):
            await service.get_provider(self.db, 1, "deepseek")
        self.assertNotIn("key-", json.dumps(self.redis.data))

    async def test_repository_rejects_cross_owner_objects_and_owner_change(self):
        other = ModelRepository(self.db, 2)
        own = await self.repository.get_provider_by_id("deepseek")
        with self.assertRaises(ValueError):
            await other.update_provider(own, name="attack")
        with self.assertRaises(ValueError):
            await other.delete_provider(own)
        with self.assertRaises(ValueError):
            await self.repository.update_provider(own, user_id=2)
        with self.assertRaises(TypeError):
            ModelRepository(self.db)
        with self.assertRaises(ValueError):
            ModelRepository(self.db, None)

    async def test_routes_ignore_forged_user_and_probe_only_own_credentials(self):
        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=2)
        body = {"base_url": "http://user2.local/v1", "models": [{"model_id": "chat-2"}], "is_enabled": True}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://test") as client:
            response = await client.get("/api/models/providers?user_id=1")
            self.assertEqual(response.json()[0]["name"], "private-2")
            self.assertNotIn("base_url", response.json()[0])
            response = await client.get("/api/models/providers/deepseek?user_id=1")
            self.assertEqual(response.json()["base_url"], "http://user2.local/v1")
            self.assertNotIn("key-", response.text)
            response = await client.post("/api/models/providers/deepseek", json={**body, "user_id": 1})
            self.assertEqual(response.status_code, 422)
            with patch.object(service, "_request_json", new_callable=AsyncMock) as remote:
                remote.return_value = {"choices": [{"message": {"role": "assistant", "content": "OK"}}]}
                response = await client.post("/api/models/providers/deepseek/test?user_id=1", json=body)
                self.assertTrue(response.json()["success"])
                self.assertEqual(remote.call_args.args[1], {"X-Owner": "2", "Authorization": "Bearer key-2"})
                remote.return_value = {"data": [{"id": "chat-2"}]}
                response = await client.post("/api/models/providers/deepseek/discover", json=body)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(remote.call_args.args[1]["Authorization"], "Bearer key-2")
            response = await client.post("/api/models/providers/deepseek", json={**body, "api_key": "new-key-2"})
            self.assertEqual(response.status_code, 200)
        self.assertEqual((await service.resolve_runtime_model(self.db, 1, "deepseek:chat-1")).api_key.get_secret_value(), "key-1")
        self.assertEqual((await service.resolve_runtime_model(self.db, 2, "deepseek:chat-2")).api_key.get_secret_value(), "new-key-2")
        await service.delete_provider(self.db, 2, "deepseek")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://test") as client:
            response = await client.get("/api/models/providers/deepseek")
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()["has_api_key"])
            self.assertEqual(response.json()["base_url"], "https://api.deepseek.com/v1")
            self.assertEqual((await client.get("/api/models/providers")).json(), [])
            with patch.object(service, "_request_json", new_callable=AsyncMock, return_value={"data": []}) as remote:
                await client.post("/api/models/providers/deepseek/discover", json=body)
                self.assertEqual(remote.call_args.args[1], {})


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
