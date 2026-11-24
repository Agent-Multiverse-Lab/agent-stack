"""模型服务的配置、持久化、缓存、三协议发现和连通性探测测试。"""

import json
import os
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import get_args
from unittest.mock import AsyncMock, patch

import httpx
from pydantic import ValidationError
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from server.entities.model import ModelProvider as ModelProviderSchema
from src.database.models import ModelProvider
from src.model import runtime, service
from src.model.utils import (
    ModelType,
    normalize_enabled_models,
    resolve_provider_api_key,
)
from test.test_model_repository import SQLiteModelTestCase

_AsyncClient = httpx.AsyncClient


def provider_kwargs(**changes):
    return {
        "provider_id": "local",
        "name": "Local",
        "base_url": "http://localhost:11434/v1/",
        "api_key": "secret-key",
        "extra_headers": {"X-Private": "secret-header"},
        "is_enabled": True,
        "enabled_models": [{"model_id": "qwen3:8b", "model_type": "ollama"}],
        **changes,
    }


def update_kwargs(**changes):
    return {
        "name": "Updated",
        "base_url": "http://localhost:11434/v1",
        "is_enabled": True,
        "enabled_models": [{"model_id": "qwen3:8b", "model_type": "ollama"}],
        **changes,
    }


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
    def test_schema_excludes_api_key_and_validates_urls_and_models(self):
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
        self.assertEqual(dumped["base_url"], "http://192.168.1.2:8000/v1")
        self.assertEqual(dumped["embedding_base_url"], "http://192.168.1.2:8001/v1")
        self.assertEqual(dumped["rerank_base_url"], "http://192.168.1.2:8002/v1/reranks")

        for bad_url in [
            "file:///tmp",
            "https://user:key@host/v1",
            "http://host/?secret=1",
            "http://host/#x",
            "http://host:bad/v1",
            "http://host/ bad",
            "http://",
        ]:
            with self.subTest(bad_url=bad_url), self.assertRaises(ValidationError):
                ModelProviderSchema(base_url=bad_url)
            with self.subTest(embedding_bad=bad_url), self.assertRaises(ValidationError):
                ModelProviderSchema(embedding_base_url=bad_url)
            with self.subTest(rerank_bad=bad_url), self.assertRaises(ValidationError):
                ModelProviderSchema(rerank_base_url=bad_url)

        for bad_models in [
            [{"model_id": "m", "model_type": "qwen"}],
            [{"model_id": "m", "category": "unknown"}],
            [{"model_id": "m", "capabilities": ["chat", "chat"]}],
            [{"model_id": "m"}, {"model_id": "m"}],
            [{"model_id": " m"}],
            [{"model_id": ""}],
        ]:
            with self.subTest(bad_models=bad_models), self.assertRaises(ValidationError):
                ModelProviderSchema(models=bad_models)

    def test_all_types_and_utils_validation(self):
        for model_type in get_args(ModelType):
            with self.subTest(model_type=model_type):
                models = normalize_enabled_models(
                    [{"model_id": "org/model:tag", "model_type": model_type}],
                    require_model_type=True,
                )
                self.assertEqual(models[0]["model_type"], model_type)

        for bad_model in [
            {"model_id": "m", "model_type": "embedding"},
            {"model_id": "m", "model_type": "qwen", "capability": "embedding"},
            {"model_id": " m", "model_type": "qwen"},
            {"model_id": "m\n", "model_type": "qwen"},
            {"model_id": "", "model_type": "qwen"},
        ]:
            with self.subTest(bad_model=bad_model), self.assertRaises(ValueError):
                normalize_enabled_models([bad_model], require_model_type=True)


class ModelServiceTest(SQLiteModelTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.redis = FakeRedis()
        self.cache_patch = patch.object(service, "get_async_redis_client", return_value=self.redis)
        self.cache_patch.start()
        self.addCleanup(self.cache_patch.stop)

    async def test_load_chat_model_resolves_context_reference_through_chat_factory(self):
        await service.create_model_provider(self.db, **provider_kwargs())

        @asynccontextmanager
        async def session_context():
            yield self.db

        model = object()
        with (
            patch.object(runtime, "session_context", session_context),
            patch.object(runtime, "build_chat_model", return_value=model) as create_model,
        ):
            self.assertIs(await runtime.load_chat_model("local/qwen3:8b"), model)
            self.assertEqual(create_model.call_args.kwargs["model_id"], "qwen3:8b")
            self.assertEqual(create_model.call_args.kwargs["protocol"], "openai_compatible")
            await service.update_model_provider(self.db, "local", **update_kwargs(is_enabled=False))
            with self.assertRaisesRegex(ValueError, "供应商已停用"):
                await runtime.load_chat_model("local/qwen3:8b")
            create_model.assert_called_once()

    async def test_crud_secret_retention_and_public_catalog(self):
        result = await service.create_model_provider(self.db, **provider_kwargs())
        self.assertTrue(result["cache_refreshed"])
        self.assertEqual(self.redis.events[0], ("delete", service.MODEL_LIST_CACHE_KEY))
        public = await service.get_model_provider(self.db, "local")
        self.assertTrue(public["has_api_key"])
        self.assertNotIn("api_key", public)
        self.assertNotIn("extra_headers", public)
        resolved = await runtime._resolve(self.db, "local/qwen3:8b")
        self.assertEqual(resolved.api_key, "secret-key")
        self.assertEqual(resolved.extra_headers["X-Private"], "secret-header")
        await service.update_model_provider(self.db, "local", **update_kwargs())
        self.assertEqual((await runtime._resolve(self.db, "local/qwen3:8b")).api_key, "secret-key")
        await service.update_model_provider(self.db, "local", **update_kwargs(api_key=""))
        self.assertFalse((await service.get_model_provider(self.db, "local"))["has_api_key"])
        self.assertEqual(len(await service.list_model_providers(self.db)), 1)
        await service.delete_model_provider(self.db, "local")
        self.assertEqual((await service.build_model_list(self.db))["models"], [])
        with self.assertRaises(LookupError):
            await runtime.validate_model(self.db, "local/qwen3:8b")

    async def test_disabled_provider_removed_from_enabled_list_and_runtime(self):
        await service.create_model_provider(self.db, **provider_kwargs())
        with Session(self.engine) as writer:
            provider = writer.get(ModelProvider, "local")
            provider.is_enabled = False
            writer.commit()
        self.assertEqual((await service.build_model_list(self.db))["models"], [])
        with self.assertRaisesRegex(ValueError, "停用"):
            await runtime.validate_model(self.db, "local/qwen3:8b")

    async def test_all_types_and_model_names_round_trip_through_database(self):
        models = [{"model_id": f"org/{kind}:tag", "model_type": kind} for kind in get_args(ModelType)]
        await service.create_model_provider(self.db, **provider_kwargs(enabled_models=models))
        for model in models:
            await runtime.validate_model(self.db, "local/" + model["model_id"])
        for invalid in ["local", "/model", "local/", " local/m"]:
            with self.assertRaises(ValueError):
                await runtime.validate_model(self.db, invalid)
        for missing in ["unknown/model", "local/missing"]:
            with self.assertRaises(LookupError):
                await runtime.validate_model(self.db, missing)

    async def test_commit_failure_rolls_back_and_does_not_refresh_cache(self):
        self.db.commit.side_effect = SQLAlchemyError("secret-key")
        with self.assertRaisesRegex(RuntimeError, "保存模型供应商失败") as error:
            await service.create_model_provider(self.db, **provider_kwargs())
        self.assertNotIn("secret-key", str(error.exception))
        self.assertEqual(self.redis.events, [])
        self.db.rollback.assert_awaited_once()
        self.assertIsNone(await self.repository.get_model_provider_by_id("local"))

    async def test_duplicate_create_preserves_cache_and_original_config(self):
        await service.create_model_provider(self.db, **provider_kwargs())
        self.redis.events.clear()
        with self.assertRaisesRegex(ValueError, "已存在"):
            await service.create_model_provider(self.db, **provider_kwargs(api_key="other-key"))
        self.assertEqual(self.redis.events, [])
        resolved = await runtime._resolve(self.db, "local/qwen3:8b")
        self.assertEqual(resolved.api_key, "secret-key")

    async def test_provider_write_and_reads_are_independent_of_redis(self):
        self.redis.error = True
        result = await service.create_model_provider(self.db, **provider_kwargs())
        self.assertFalse(result["cache_refreshed"])
        with Session(self.engine) as verifier:
            self.assertIsNotNone(verifier.scalar(select(ModelProvider)))
        self.assertEqual((await service.build_model_list(self.db))["models"][0]["id"], "local/qwen3:8b")
        self.assertEqual(self.redis.events, [])

    async def test_resolve_provider_api_key_supports_env_and_plaintext(self):
        clean_env = {key: value for key, value in os.environ.items() if key != "DEEPSEEK_API_KEY"}
        with patch.dict(os.environ, clean_env, clear=True), patch.object(service.sys_config, "deepseek_api_key", ""):
            self.assertEqual(resolve_provider_api_key("DEEPSEEK_API_KEY"), "")
        with patch.dict(os.environ, {**clean_env, "DEEPSEEK_API_KEY": " env-deepseek-key "}, clear=True):
            self.assertEqual(resolve_provider_api_key("DEEPSEEK_API_KEY"), "env-deepseek-key")
        with patch.dict(os.environ, clean_env, clear=True), patch.object(service.sys_config, "deepseek_api_key", "cfg-deepseek-key"):
            self.assertEqual(resolve_provider_api_key("DEEPSEEK_API_KEY"), "cfg-deepseek-key")

        await service.create_model_provider(
            self.db,
            **provider_kwargs(provider_id="custom", api_key="sk-plain-123"),
        )
        public = await service.get_model_provider(self.db, "custom")
        self.assertNotIn("api_key", public)
        self.assertTrue(public["has_api_key"])
        resolved = await runtime._resolve(self.db, "custom/qwen3:8b")
        self.assertEqual(resolved.api_key, "sk-plain-123")

    async def test_cache_rebuild_database_error_is_soft_after_write_and_strict_at_startup(self):
        with patch.object(
            service,
            "build_model_list",
            new=AsyncMock(side_effect=SQLAlchemyError("database unavailable")),
        ):
            self.assertFalse(await service.refresh_model_list_cache(self.db))
            with self.assertRaises(SQLAlchemyError):
                await service.refresh_model_list_cache(
                    self.db,
                    raise_on_database_error=True,
                )

    async def test_provider_writes_refresh_public_model_list(self):
        await service.create_model_provider(self.db, **provider_kwargs())
        created = json.loads(self.redis.data[service.MODEL_LIST_CACHE_KEY])
        self.assertEqual(created["models"][0]["id"], "local/qwen3:8b")
        await service.update_model_provider(self.db, "local", **update_kwargs())
        await service.delete_model_provider(self.db, "local")
        deleted = json.loads(self.redis.data[service.MODEL_LIST_CACHE_KEY])
        self.assertEqual(deleted["models"], [])
        self.assertGreaterEqual(
            self.redis.events.count(("delete", service.MODEL_LIST_CACHE_KEY)),
            3,
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
        await service.create_model_provider(self.db, **provider_kwargs())
        await service.create_model_provider(
            self.db,
            **provider_kwargs(
                provider_id="anthropic",
                name="Anthropic",
                base_url="https://api.anthropic.com",
                protocol="anthropic",
                api_key="sk-ant",
                enabled_models=[{"model_id": "claude-sonnet-4-6", "model_type": "claude"}],
            ),
        )
        await service.create_model_provider(
            self.db,
            **provider_kwargs(
                provider_id="gemini",
                name="Gemini",
                base_url="https://generativelanguage.googleapis.com",
                protocol="gemini",
                api_key="AIza-key",
                enabled_models=[{"model_id": "gemini-2.5-pro", "model_type": "gemini"}],
            ),
        )

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
            self.assertEqual(await service.discover_models(self.db, "local"), ["text", "vision"])

        def anthropic_handler(request):
            self.assertEqual(request.url.path, "/v1/models")
            self.assertEqual(request.headers["x-api-key"], "sk-ant")
            return httpx.Response(200, json={"data": [{"id": "claude-sonnet-4-6"}]})

        with self.http_mock(anthropic_handler):
            self.assertEqual(await service.discover_models(self.db, "anthropic"), ["claude-sonnet-4-6"])

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
            self.assertEqual(await service.discover_models(self.db, "gemini"), ["gemini-2.5-pro"])

    async def test_chat_probe_on_disabled_provider_uses_build_chat_model(self):
        await service.create_model_provider(self.db, **provider_kwargs(is_enabled=False))
        fake_chat = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content="OK", tool_calls=[])))
        with patch.object(service, "build_chat_model", return_value=fake_chat) as build_chat:
            result = await service.test_model_connection(self.db, "local/qwen3:8b")
        self.assertTrue(result["success"])
        build_chat.assert_called_once_with(
            protocol="openai_compatible",
            model_id="qwen3:8b",
            api_key="secret-key",
            base_url="http://localhost:11434/v1",
            extra_headers={"X-Private": "secret-header"},
        )
        fake_chat.ainvoke.assert_awaited_once_with("Reply with OK.")
        self.assertFalse((await service.get_model_provider(self.db, "local"))["is_enabled"])

    async def test_http_failures_are_sanitized_and_redirects_not_followed(self):
        await service.create_model_provider(self.db, **provider_kwargs())
        for status in [301, 401, 429, 500]:
            requests = []

            def handler(request):
                requests.append(request)
                return httpx.Response(status, text="secret-key secret-header", headers={"Location": "https://elsewhere.example"})

            with self.subTest(status=status), self.http_mock(handler):
                with self.assertRaises(service.ModelConnectionError) as error:
                    await service.discover_models(self.db, "local")
                self.assertEqual(str(error.exception), "http_error")
                self.assertEqual(error.exception.status_code, status)
                self.assertEqual(len(requests), 1)

            fake_chat = SimpleNamespace(
                ainvoke=AsyncMock(
                    side_effect=httpx.HTTPStatusError(
                        "secret-key",
                        request=httpx.Request("POST", "https://example.com"),
                        response=httpx.Response(status),
                    )
                )
            )
            with self.subTest(probe_status=status), patch.object(service, "build_chat_model", return_value=fake_chat):
                result = await service.test_model_connection(self.db, "local/qwen3:8b")
                self.assertFalse(result["success"])
                self.assertEqual(result["status_code"], status)
                self.assertNotIn("secret", json.dumps(result))

    async def test_timeout_transport_and_malformed_response(self):
        await service.create_model_provider(self.db, **provider_kwargs())
        for exception, code in [(httpx.ReadTimeout, "timeout"), (httpx.ConnectError, "connection_error")]:
            fake_chat = SimpleNamespace(
                ainvoke=AsyncMock(side_effect=exception("secret-key", request=httpx.Request("POST", "https://example.com")))
            )
            with self.subTest(code=code), patch.object(service, "build_chat_model", return_value=fake_chat):
                result = await service.test_model_connection(self.db, "local/qwen3:8b")
                self.assertEqual(result["error"], code)

        for response in [SimpleNamespace(content=[], tool_calls=[]), SimpleNamespace(content=None, tool_calls=[])]:
            fake_chat = SimpleNamespace(ainvoke=AsyncMock(return_value=response))
            with self.subTest(response=response), patch.object(service, "build_chat_model", return_value=fake_chat):
                self.assertEqual((await service.test_model_connection(self.db, "local/qwen3:8b"))["error"], "invalid_response")

        for payload in [{}, {"data": [None]}, {"data": [{"id": ""}]}]:
            with self.subTest(payload=payload), self.http_mock(lambda request: httpx.Response(200, json=payload)):
                with self.assertRaises(service.ModelConnectionError):
                    await service.discover_models(self.db, "local")
