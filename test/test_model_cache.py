"""PostgreSQL 模型目录投影与 Redis read-through cache 测试。"""

import json
from unittest.mock import patch

from redis.exceptions import ConnectionError as RedisConnectionError

from server.service import model_service as service
from test.test_model_repository import SQLiteModelTestCase


class FakeRedis:
    def __init__(self, cached=None, error: Exception | None = None) -> None:
        self.cached = cached
        self.error = error
        self.get_key = None
        self.set_arguments = None

    async def get(self, key):
        if self.error is not None:
            raise self.error
        self.get_key = key
        return self.cached

    async def set(self, key, value, *, ex):
        if self.error is not None:
            raise self.error
        self.set_arguments = (key, value, ex)


class ModelCatalogTest(SQLiteModelTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await self.insert_provider(
            "dashscope",
            name="Qwen",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            enabled_models=[
                {"model_id": "qwen3.8-max", "model_type": "qwen"},
            ],
        )
        await self.insert_provider(
            "disabled",
            name="Disabled",
            is_enabled=False,
            enabled_models=[
                {"model_id": "hidden", "model_type": "openai"},
            ],
        )
        await self.db.commit()

    async def test_builds_public_catalog_from_enabled_database_providers(self):
        catalog = await service.build_model_list(self.db)

        self.assertEqual(["dashscope/qwen3.8-max"], [item.id for item in catalog.models])
        model = catalog.models[0]
        self.assertEqual(
            (model.display_name, model.version, model.icon),
            ("Qwen", "3.8 Max", "qwen"),
        )
        self.assertTrue(model.is_available)

    async def test_cache_hit_returns_strict_cached_catalog_without_rewrite(self):
        cached_catalog = {
            "default_model": "dashscope/cached-model",
            "fallback_model": "",
            "flash_model": "",
            "image_model": "",
            "models": [
                {
                    "id": "dashscope/cached-model",
                    "name": "cached-model",
                    "display_name": "Qwen",
                    "version": "cached-model",
                    "provider": "dashscope",
                    "icon": "qwen",
                    "is_available": True,
                    "is_default": True,
                    "is_fallback": False,
                    "is_flash": False,
                }
            ],
        }
        redis = FakeRedis(json.dumps(cached_catalog).encode())

        with patch.object(service, "get_async_redis_client", return_value=redis):
            result = await service.list_models(self.db)

        self.assertEqual(cached_catalog, result.model_dump())
        self.assertEqual(service.MODEL_LIST_CACHE_KEY, redis.get_key)
        self.assertIsNone(redis.set_arguments)

    async def test_cache_miss_builds_from_database_and_sets_ttl(self):
        redis = FakeRedis()

        with patch.object(service, "get_async_redis_client", return_value=redis):
            result = await service.list_models(self.db)

        key, raw_catalog, ttl = redis.set_arguments
        self.assertEqual(service.MODEL_LIST_CACHE_KEY, key)
        self.assertEqual(service.MODEL_LIST_CACHE_TTL_SECONDS, ttl)
        self.assertEqual(result.model_dump(), json.loads(raw_catalog))

    async def test_invalid_cache_and_redis_failure_fall_back_to_database(self):
        for redis in (
            FakeRedis(b'{"models":[{"id":"incomplete"}]}'),
            FakeRedis(error=RedisConnectionError("unavailable")),
        ):
            with self.subTest(redis=redis), patch.object(
                service,
                "get_async_redis_client",
                return_value=redis,
            ):
                result = await service.list_models(self.db)

            self.assertEqual(
                ["dashscope/qwen3.8-max"],
                [item.id for item in result.models],
            )
