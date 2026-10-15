"""模型服务的配置、持久化、缓存和 HTTP 合同测试，不访问真实供应商。"""

import json
import unittest
from typing import get_args
from unittest.mock import AsyncMock, patch

import httpx
from pydantic import ValidationError
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from server.service import model_service as service
from src.database.models import ModelProvider
from src.model.provider import EnabledModel, ModelProviderCreate, ModelProviderUpdate, ModelType
from test.test_model_repository import SQLiteModelTestCase

_AsyncClient = httpx.AsyncClient


def provider_config(**changes):
    return ModelProviderCreate.model_validate(
        {
            "provider_id": "local",
            "name": "Local",
            "base_url": "http://localhost:11434/v1/",
            "api_key": "secret-key",
            "extra_headers": {"X-Private": "secret-header"},
            "is_enabled": True,
            "enabled_models": [{"model_id": "qwen3:8b", "model_type": "ollama", "body_overrides": {"temperature": 0.2}}],
            **changes,
        }
    )


def update_config(**changes):
    return ModelProviderUpdate.model_validate(
        {
            "name": "Updated",
            "base_url": "http://localhost:11434/v1",
            "is_enabled": True,
            "enabled_models": [{"model_id": "qwen3:8b", "model_type": "ollama"}],
            **changes,
        }
    )


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
    def test_all_types_and_local_keyless_addresses(self):
        for model_type in get_args(ModelType):
            with self.subTest(model_type=model_type):
                config = provider_config(
                    api_key="",
                    base_url="http://192.168.1.2:8000/v1/",
                    enabled_models=[
                        {
                            "model_id": "org/model:tag",
                            "model_type": model_type,
                        }
                    ],
                )
                self.assertEqual(config.base_url, "http://192.168.1.2:8000/v1")
                self.assertEqual(config.enabled_models[0].model_type, model_type)
        config = provider_config()
        self.assertNotIn("secret-key", repr(config))
        self.assertNotIn("secret-header", config.model_dump_json())

    def test_rejects_unknown_types_duplicate_models_and_non_chat_schema(self):
        for model in [
            {"model_id": "m", "model_type": "embedding"},
            {"model_id": "m", "model_type": "qwen", "capability": "embedding"},
            {"model_id": " m", "model_type": "qwen"},
            {"model_id": "m\n", "model_type": "qwen"},
            {"model_id": "", "model_type": "qwen"},
        ]:
            with self.subTest(model=model), self.assertRaises(ValidationError):
                EnabledModel.model_validate(model)
        with self.assertRaises(ValidationError):
            provider_config(enabled_models=[{"model_id": "m", "model_type": "qwen"}] * 2)

    def test_rejects_reserved_overrides_and_non_json(self):
        for overrides in [
            {key: "forbidden"}
            for key in (
                "model",
                "messages",
                "stream",
                "input",
                "query",
                "documents",
                "api_key",
                "base_url",
                "headers",
                "extra_body",
            )
        ] + [{"temperature": float("nan")}, {"bad": object()}, {"bad": {1, 2}}]:
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                EnabledModel(model_id="m", model_type="qwen", body_overrides=overrides)

    def test_validates_url_headers_key_and_provider_id(self):
        invalid = (
            [{"base_url": value} for value in ["file:///tmp", "https://user:key@host/v1", "http://host/?secret=1", "http://host/#x", "http://host:bad/v1", "http://host/ bad", "http://"]]
            + [{"extra_headers": value} for value in [{"Authorization": "x"}, {"Host": "x"}, {"Content-Length": "1"}, {"X-A": "a", "x-a": "b"}, {"X-A": "x\r\ny"}, {"bad header": "x"}]]
            + [{"api_key": "key\n"}, {"provider_id": "bad:id"}, {"protocol": "unknown"}, {"is_enabled": "false"}]
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                provider_config(**changes)
        with self.assertRaises(ValidationError):
            update_config(api_key=None)


class ModelServiceTest(SQLiteModelTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.redis = FakeRedis()
        self.cache_patch = patch.object(service, "get_async_redis_client", return_value=self.redis)
        self.cache_patch.start()
        self.addCleanup(self.cache_patch.stop)
        async def mock_target(base_url):
            return httpx.URL(base_url), "localhost:11434", "localhost"
        target_patch = patch.object(service, "resolve_public_target", side_effect=mock_target)
        target_patch.start()
        self.addCleanup(target_patch.stop)

    async def test_crud_secret_retention_and_public_catalog(self):
        result = await service.create_provider(self.db, provider_config())
        self.assertTrue(result.cache_refreshed)
        self.assertEqual(self.redis.events[0], ("delete", service.MODEL_LIST_CACHE_KEY))
        public = await service.get_provider(self.db, "local")
        self.assertTrue(public.has_api_key)
        self.assertNotIn("secret-key", public.model_dump_json())
        self.assertNotIn("extra_headers", public.model_dump())
        connection = await service.resolve_runtime_model(self.db, "local/qwen3:8b")
        self.assertEqual(connection.api_key.get_secret_value(), "secret-key")
        self.assertEqual(connection.request_headers()["X-Private"], "secret-header")
        self.assertNotIn("secret-header", repr(connection))
        self.assertNotIn("secret-key", connection.model_dump_json())
        await service.update_provider(self.db, "local", update_config())
        self.assertEqual((await service.resolve_runtime_model(self.db, "local/qwen3:8b")).api_key.get_secret_value(), "secret-key")
        await service.update_provider(self.db, "local", update_config(api_key=""))
        self.assertFalse((await service.get_provider(self.db, "local")).has_api_key)
        self.assertEqual(len(await service.list_providers(self.db)), 1)
        await service.delete_provider(self.db, "local")
        self.assertEqual(await service.list_enabled_models(self.db), [])
        with self.assertRaises(LookupError):
            await service.resolve_runtime_model(self.db, "local/qwen3:8b")

    async def test_disabled_provider_removed_from_enabled_list_and_runtime(self):
        await service.create_provider(self.db, provider_config())
        with Session(self.engine) as writer:
            provider = writer.get(ModelProvider, "local")
            provider.is_enabled = False
            writer.commit()
        self.assertEqual(await service.list_enabled_models(self.db), [])
        with self.assertRaisesRegex(ValueError, "停用"):
            await service.resolve_runtime_model(self.db, "local/qwen3:8b")

    async def test_all_types_and_model_names_round_trip_through_database(self):
        models = [{"model_id": f"org/{kind}:tag", "model_type": kind} for kind in get_args(ModelType)]
        await service.create_provider(self.db, provider_config(enabled_models=models))
        for model in models:
            resolved = await service.resolve_runtime_model(self.db, "local/" + model["model_id"])
            self.assertEqual(resolved.model_id, model["model_id"])
            self.assertEqual(resolved.model_type, model["model_type"])
        for invalid in ["local", "/model", "local/"]:
            with self.assertRaises(ValueError):
                await service.resolve_runtime_model(self.db, invalid)
        for missing in ["unknown/model", "local/missing"]:
            with self.assertRaises(LookupError):
                await service.resolve_runtime_model(self.db, missing)

    async def test_commit_failure_rolls_back_and_does_not_refresh_cache(self):
        self.db.commit.side_effect = SQLAlchemyError("secret-key")
        with self.assertRaisesRegex(RuntimeError, "保存模型供应商失败") as error:
            await service.create_provider(self.db, provider_config())
        self.assertNotIn("secret-key", str(error.exception))
        self.assertEqual(self.redis.events, [])
        self.db.rollback.assert_awaited_once()
        self.assertIsNone(await self.repository.get_provider_by_id("local"))

    async def test_duplicate_create_preserves_cache_and_original_config(self):
        await service.create_provider(self.db, provider_config())
        self.redis.events.clear()
        with self.assertRaisesRegex(ValueError, "已存在"):
            await service.create_provider(self.db, provider_config(api_key="other-key"))
        self.assertEqual(self.redis.events, [])
        resolved = await service.resolve_runtime_model(self.db, "local/qwen3:8b")
        self.assertEqual(resolved.api_key.get_secret_value(), "secret-key")

    async def test_provider_write_and_reads_are_independent_of_redis(self):
        self.redis.error = True
        result = await service.create_provider(self.db, provider_config())
        self.assertFalse(result.cache_refreshed)
        with Session(self.engine) as verifier:
            self.assertIsNotNone(verifier.scalar(select(ModelProvider)))
        self.assertEqual((await service.list_enabled_models(self.db))[0].id, "local/qwen3:8b")
        self.assertEqual(self.redis.events, [])

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
        await service.create_provider(self.db, provider_config())
        created = json.loads(self.redis.data[service.MODEL_LIST_CACHE_KEY])
        self.assertEqual(created["models"][0]["id"], "local/qwen3:8b")
        await service.update_provider(self.db, "local", update_config())
        await service.delete_provider(self.db, "local")
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

    async def test_discovery_deduplicates_filters_and_does_not_enable_models(self):
        await service.create_provider(self.db, provider_config())

        def handler(request):
            self.assertEqual(str(request.url), "http://localhost:11434/v1/models")
            self.assertEqual(request.method, "GET")
            self.assertEqual(request.headers["authorization"], "Bearer secret-key")
            self.assertEqual(request.headers["x-private"], "secret-header")
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

        with self.http_mock(handler):
            self.assertEqual(await service.discover_models(self.db, "local"), ["text", "vision"])
        self.assertEqual(len((await service.get_provider(self.db, "local")).enabled_models), 1)

    async def test_chat_probe_on_disabled_provider_uses_overrides_and_saved_model(self):
        await service.create_provider(self.db, provider_config(is_enabled=False))

        def handler(request):
            body = json.loads(request.content)
            self.assertEqual(request.url.path, "/v1/chat/completions")
            self.assertEqual(body["model"], "qwen3:8b")
            self.assertEqual(body["temperature"], 0.2)
            self.assertFalse(body["stream"])
            self.assertEqual(body["messages"][0]["role"], "user")
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "OK"}}]})

        with self.http_mock(handler):
            result = await service.test_model_connection(self.db, "local/qwen3:8b")
        self.assertTrue(result.success)
        self.assertGreaterEqual(result.elapsed_ms, 0)
        self.assertFalse((await service.get_provider(self.db, "local")).is_enabled)

    async def test_http_failures_are_sanitized_and_redirects_not_followed(self):
        await service.create_provider(self.db, provider_config())
        for status in [301, 401, 429, 500]:
            requests = []

            def handler(request):
                requests.append(request)
                return httpx.Response(status, text="secret-key secret-header", headers={"Location": "https://elsewhere.example"})

            with self.subTest(status=status), self.http_mock(handler):
                result = await service.test_model_connection(self.db, "local/qwen3:8b")
                self.assertFalse(result.success)
                self.assertEqual(result.status_code, status)
                self.assertNotIn("secret", result.model_dump_json())
                self.assertEqual(len(requests), 1)
                with self.assertRaises(service.ModelConnectionError) as error:
                    await service.discover_models(self.db, "local")
                self.assertEqual(str(error.exception), "http_error")

    async def test_timeout_transport_and_malformed_response(self):
        await service.create_provider(self.db, provider_config())
        for exception, code in [(httpx.ReadTimeout, "timeout"), (httpx.ConnectError, "connection_error")]:

            def handler(request):
                raise exception("secret-key", request=request)

            with self.subTest(code=code), self.http_mock(handler):
                result = await service.test_model_connection(self.db, "local/qwen3:8b")
                self.assertEqual(result.error, code)
        for payload in [{}, {"choices": []}, {"choices": [None]}, {"choices": [{"message": {"role": "user", "content": "bad"}}]}]:
            with self.subTest(payload=payload), self.http_mock(lambda request: httpx.Response(200, json=payload)):
                self.assertEqual((await service.test_model_connection(self.db, "local/qwen3:8b")).error, "invalid_response")
        for payload in [{}, {"data": [None]}, {"data": [{"id": ""}]}]:
            with self.subTest(payload=payload), self.http_mock(lambda request: httpx.Response(200, json=payload)):
                with self.assertRaises(service.ModelConnectionError):
                    await service.discover_models(self.db, "local")
