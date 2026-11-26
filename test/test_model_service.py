"""模型服务的校验、缓存、三协议发现和连通性探测测试。"""

import json
import os
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from server.entities.model import ModelProvider as ModelProviderSchema
from src.configs import config as sys_config
from src.database.models import ModelProvider
from src.model import service
from src.model.utils import (
    normalize_base_url,
    normalize_enabled_models,
    normalize_optional_url,
    resolve_provider_api_key,
)
from test.test_model_repository import SQLiteModelTestCase

_AsyncClient = httpx.AsyncClient


class FakeRedis:
    def __init__(self):
        self.data = {}
        self.events = []
        self.error = False

    async def get(self, key):
        if self.error:
            raise RedisConnectionError("private connection error")
        return self.data.get(key)

    async def set(self, key, value, *, ex):
        if self.error:
            raise RedisConnectionError("private connection error")
        self.events.append(("set", key, ex))
        self.data[key] = value

    async def delete(self, key):
        if self.error:
            raise RedisConnectionError("private connection error")
        self.events.append(("delete", key))
        self.data.pop(key, None)


class ModelValidationTest(unittest.TestCase):
    def test_schema_excludes_api_key_and_validates_urls(self):
        provider = ModelProviderSchema(
            provider_id="local",
            name="Local",
            base_url="http://192.168.1.2:8000/v1/",
            embedding_base_url="http://192.168.1.2:8001/v1/",
            rerank_base_url="http://192.168.1.2:8002/v1/reranks/",
            api_key="secret-key",
            is_enabled=True,
            has_api_key=True,
            models=[{"model_id": "m1", "category": "embedding", "capabilities": []}],
        )
        dumped = provider.model_dump()
        self.assertNotIn("api_key", dumped)

        self.assertEqual(normalize_base_url("http://192.168.1.2:8000/v1/"), "http://192.168.1.2:8000/v1")
        self.assertEqual(normalize_optional_url(""), "")
        self.assertEqual(normalize_optional_url("http://192.168.1.2:8002/v1/reranks/"), "http://192.168.1.2:8002/v1/reranks")

        for bad_url in [
            "file:///tmp",
            "https://user:key@host/v1",
            "http://host/?secret=1",
            "http://host/#x",
            "http://host:bad/v1",
            "http://host/ bad",
            "http://",
        ]:
            with self.subTest(bad_url=bad_url), self.assertRaises(ValueError):
                normalize_base_url(bad_url)
            with self.subTest(optional_bad=bad_url), self.assertRaises(ValueError):
                normalize_optional_url(bad_url)

    def test_normalize_enabled_models_validation(self):
        models = normalize_enabled_models(
            [{"model_id": "org/model:tag", "category": "chat", "capabilities": ["vision"]}]
        )
        self.assertEqual(
            models,
            [{"model_id": "org/model:tag", "category": "chat", "capabilities": ["vision"]}],
        )

        for bad_model in [
            {"model_id": "m", "model_type": "qwen"},
            {"model_id": "m", "category": "unknown"},
            {"model_id": "m", "capability": "embedding"},
            {"model_id": " m"},
            {"model_id": "m\n"},
            {"model_id": ""},
        ]:
            with self.subTest(bad_model=bad_model), self.assertRaises(ValueError):
                normalize_enabled_models([bad_model])


class ModelServiceTest(SQLiteModelTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.redis = FakeRedis()
        self.cache_patch = patch.object(service, "get_async_redis_client", return_value=self.redis)
        self.cache_patch.start()
        self.addCleanup(self.cache_patch.stop)

    async def test_resolve_provider_api_key_supports_env_and_plaintext(self):
        clean_env = {key: value for key, value in os.environ.items() if key != "DEEPSEEK_API_KEY"}
        with patch.dict(os.environ, clean_env, clear=True), patch.object(sys_config, "deepseek_api_key", ""):
            self.assertEqual(resolve_provider_api_key("DEEPSEEK_API_KEY"), "")
        with patch.dict(os.environ, {**clean_env, "DEEPSEEK_API_KEY": " env-deepseek-key "}, clear=True):
            self.assertEqual(resolve_provider_api_key("DEEPSEEK_API_KEY"), "env-deepseek-key")
        with patch.dict(os.environ, clean_env, clear=True), patch.object(sys_config, "deepseek_api_key", "cfg-deepseek-key"):
            self.assertEqual(resolve_provider_api_key("DEEPSEEK_API_KEY"), "cfg-deepseek-key")

        await self.insert_provider("custom", api_key="sk-plain-123")
        await self.db.commit()
        public = await service.get_model_provider(self.db, "custom")
        self.assertNotIn("api_key", public)
        self.assertTrue(public["has_api_key"])
        provider, _ = await self.repository.require_model("custom:qwen3:8b")
        self.assertEqual(resolve_provider_api_key(provider.api_key or ""), "sk-plain-123")

        resolved = await service.get_enabled_model(self.db, "custom:qwen3:8b", category="chat")
        self.assertEqual(resolved.model_ref, "custom:qwen3:8b")
        self.assertEqual(resolved.provider_id, "custom")
        self.assertEqual(resolved.model_id, "qwen3:8b")
        with self.assertRaises(ValueError):
            await service.get_enabled_model(self.db, "", category="chat")

    async def test_provider_crud_lifecycle(self):
        created = await service.create_model_provider(
            self.db,
            provider_id="custom",
            name="Custom Anthropic",
            protocol="anthropic",
            base_url="https://api.anthropic.com/",
            api_key="sk-ant",
            is_enabled=True,
            models=[{"model_id": "claude-sonnet-5-5", "category": "chat", "capabilities": []}],
        )
        self.assertEqual(created, {"provider_id": "custom", "cache_refreshed": True})

        fetched = await service.get_model_provider(self.db, "custom")
        self.assertEqual(fetched["protocol"], "anthropic")
        self.assertEqual(fetched["base_url"], "https://api.anthropic.com")
        self.assertTrue(fetched["has_api_key"])
        self.assertNotIn("api_key", fetched)

        with self.assertRaises(service.ModelProviderConflictError):
            await service.create_model_provider(
                self.db,
                provider_id="custom",
                name="Duplicate",
                base_url="https://api.anthropic.com",
            )

        await service.update_model_provider(
            self.db,
            "custom",
            base_url="https://api.anthropic.com",
            is_enabled=True,
            models=[{"model_id": "claude-opus-5-5", "category": "chat", "capabilities": []}],
        )
        row = await self.repository.get_model_provider_by_id("custom")
        self.assertEqual(row.name, "Custom Anthropic")
        self.assertEqual(row.protocol, "anthropic")
        self.assertEqual(row.api_key, "sk-ant")

        deleted = await service.delete_model_provider(self.db, "custom")
        self.assertEqual(deleted, {"provider_id": "custom", "cache_refreshed": True})
        with self.assertRaises(LookupError):
            await service.get_model_provider(self.db, "custom")
        with self.assertRaises(LookupError):
            await service.delete_model_provider(self.db, "custom")

    async def test_commit_failure_rolls_back_and_does_not_refresh_cache(self):
        await self.insert_provider("local")
        await self.db.commit()
        self.db.commit.side_effect = SQLAlchemyError("secret-key")
        with self.assertRaisesRegex(RuntimeError, "更新模型供应商失败") as error:
            await service.update_model_provider(
                self.db,
                "local",
                base_url="http://localhost:11434/v1",
                is_enabled=False,
                models=[],
            )
        self.assertNotIn("secret-key", str(error.exception))
        self.assertEqual(self.redis.events, [])
        self.db.rollback.assert_awaited_once()

    async def test_save_settings_is_independent_of_redis_and_refreshes_catalog(self):
        await self.insert_provider("local")
        await self.db.commit()
        self.redis.error = True
        result = await service.update_model_provider(
            self.db,
            "local",
            base_url="http://localhost:11434/v1",
            is_enabled=True,
            models=[{"model_id": "qwen3:8b", "category": "chat", "capabilities": []}],
        )
        self.assertFalse(result["cache_refreshed"])
        with Session(self.engine) as verifier:
            self.assertIsNotNone(verifier.scalar(select(ModelProvider)))
        catalog = await service.build_model_catalog(self.db, category="chat")
        self.assertEqual(catalog["local"]["models"][0]["model_id"], "qwen3:8b")
        self.assertEqual(self.redis.events, [])

        self.redis.error = False
        result = await service.update_model_provider(
            self.db,
            "local",
            base_url="http://localhost:11434/v1",
            is_enabled=False,
            models=[{"model_id": "qwen3:8b", "category": "chat", "capabilities": []}],
        )
        self.assertTrue(result["cache_refreshed"])
        cached = json.loads(self.redis.data[service.MODEL_CATALOG_CACHE_KEY])
        self.assertEqual(cached, {})
        self.assertIn(("delete", service.MODEL_CATALOG_CACHE_KEY), self.redis.events)

    async def test_cache_rebuild_database_error_is_soft_after_write_and_strict_at_startup(self):
        with patch.object(
            service,
            "build_model_catalog",
            new=AsyncMock(side_effect=SQLAlchemyError("database unavailable")),
        ):
            self.assertFalse(await service.refresh_model_list_cache(self.db))
            with self.assertRaises(SQLAlchemyError):
                await service.refresh_model_list_cache(
                    self.db,
                    raise_on_database_error=True,
                )

    def http_mock(self, handler):
        return patch.object(
            service.httpx,
            "AsyncClient",
            side_effect=lambda **kwargs: _AsyncClient(
                transport=httpx.MockTransport(handler),
                **kwargs,
            ),
        )

    async def test_discovery_supports_openai_anthropic_and_gemini(self):
        await self.insert_provider("local")
        await self.insert_provider(
            "anthropic",
            name="Anthropic",
            base_url="https://api.anthropic.com",
            protocol="anthropic",
            api_key="sk-ant",
            enabled_models=[{"model_id": "claude-sonnet-4-6", "category": "chat", "capabilities": []}],
        )
        await self.insert_provider(
            "gemini",
            name="Gemini",
            base_url="https://generativelanguage.googleapis.com",
            protocol="gemini",
            api_key="AIza-key",
            enabled_models=[{"model_id": "gemini-2.5-pro", "category": "chat", "capabilities": []}],
        )
        await self.db.commit()

        def openai_handler(request):
            self.assertEqual(str(request.url), "http://localhost:11434/v1/models")
            self.assertEqual(request.headers["authorization"], "Bearer secret-key")
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "text"},
                        {"id": "text"},
                        {"id": "vision", "capabilities": ["chat", "vision"]},
                        {"id": "vector", "type": "embedding"},
                        {"id": "rank", "capabilities": ["rerank"]},
                        {"id": "not-chat", "capabilities": {"chat": False}},
                    ]
                },
            )

        with self.http_mock(openai_handler):
            discovered = await service.discover_provider_models(
                self.db, "local", base_url="http://localhost:11434/v1"
            )
            self.assertEqual([item["model_id"] for item in discovered], ["text", "vision"])

        def anthropic_handler(request):
            self.assertEqual(request.url.path, "/v1/models")
            self.assertEqual(request.headers["x-api-key"], "sk-ant")
            return httpx.Response(200, json={"data": [{"id": "claude-sonnet-4-6"}]})

        with self.http_mock(anthropic_handler):
            discovered = await service.discover_provider_models(
                self.db, "anthropic", base_url="https://api.anthropic.com"
            )
            self.assertEqual([item["model_id"] for item in discovered], ["claude-sonnet-4-6"])

        def gemini_handler(request):
            self.assertEqual(request.url.path, "/v1beta/models")
            self.assertEqual(request.headers["x-goog-api-key"], "AIza-key")
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
                        {"name": "models/gemini-embedding-001", "supportedGenerationMethods": ["embedContent"]},
                    ]
                },
            )

        with self.http_mock(gemini_handler):
            discovered = await service.discover_provider_models(
                self.db, "gemini", base_url="https://generativelanguage.googleapis.com"
            )
            self.assertEqual([item["model_id"] for item in discovered], ["gemini-2.5-pro"])

    async def test_http_failures_are_sanitized_and_redirects_not_followed(self):
        await self.insert_provider("local")
        await self.db.commit()
        for status in [301, 401, 429, 500]:
            requests = []

            def handler(request):
                requests.append(request)
                return httpx.Response(status, text="secret-key secret-header", headers={"Location": "https://elsewhere.example"})

            with self.subTest(status=status), self.http_mock(handler):
                with self.assertRaises(service.ModelConnectionError) as error:
                    await service.discover_provider_models(
                        self.db, "local", base_url="http://localhost:11434/v1"
                    )
                self.assertEqual(str(error.exception), "http_error")
                self.assertEqual(error.exception.status_code, status)
                self.assertEqual(len(requests), 1)

            with self.subTest(probe_status=status), self.http_mock(handler):
                result = await service.test_provider_connection(
                    self.db, "local", base_url="http://localhost:11434/v1"
                )
                self.assertFalse(result["success"])
                self.assertEqual(result["status_code"], status)
                self.assertNotIn("secret", json.dumps(result))

    async def test_timeout_transport_and_malformed_response(self):
        await self.insert_provider("local")
        await self.db.commit()
        for exception, code in [(httpx.ReadTimeout, "timeout"), (httpx.ConnectError, "connection_error")]:
            def fail_handler(request, exc=exception):
                raise exc("secret-key", request=request)

            with self.subTest(code=code), self.http_mock(fail_handler):
                result = await service.test_provider_connection(
                    self.db, "local", base_url="http://localhost:11434/v1"
                )
                self.assertEqual(result["error"], code)

        for payload in [{}, {"data": [None]}, {"data": [{"id": ""}]}]:
            with self.subTest(payload=payload), self.http_mock(lambda request, p=payload: httpx.Response(200, json=p)):
                with self.assertRaises(service.ModelConnectionError):
                    await service.discover_provider_models(
                        self.db, "local", base_url="http://localhost:11434/v1"
                    )
