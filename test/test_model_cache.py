"""模型目录展示字段与 Redis read-through cache 测试。"""

import json
import unittest
from unittest.mock import patch

from redis.exceptions import ConnectionError as RedisConnectionError

from src.model import model_cache


class FakeRedis:
    def __init__(self, cached=None, error: Exception | None = None) -> None:
        self.cached = cached
        self.error = error
        self.set_arguments = None

    async def get(self, key):
        if self.error is not None:
            raise self.error
        self.get_key = key
        return self.cached

    async def set(self, key, value, *, ex):
        self.set_arguments = (key, value, ex)


class ModelCatalogTest(unittest.TestCase):
    def test_builds_public_name_version_and_icon_from_config(self):
        catalog = model_cache.build_model_catalog()
        by_id = {model["id"]: model for model in catalog["models"]}

        self.assertEqual("Qwen", by_id["dashscope/qwen3.8-max"]["display_name"])
        self.assertEqual("3.8 Max", by_id["dashscope/qwen3.8-max"]["version"])
        self.assertEqual("qwen", by_id["dashscope/qwen3.8-max"]["icon"])
        self.assertEqual("V4 Pro", by_id["deepseek/deepseek-v4-pro"]["version"])
        self.assertEqual("4o Mini", by_id["openai/gpt-4o-mini"]["version"])

    def test_marks_only_loader_supported_models_available(self):
        catalog = model_cache.build_model_catalog()
        by_id = {model["id"]: model for model in catalog["models"]}

        self.assertTrue(by_id["dashscope/qwen3.8-max"]["is_available"])
        self.assertFalse(by_id["gemini/gemini-3-pro"]["is_available"])
        self.assertFalse(model_cache.is_model_available("gemini/gemini-3-pro"))


class ModelCacheTest(unittest.IsolatedAsyncioTestCase):
    async def test_cache_hit_returns_cached_catalog_without_rewrite(self):
        cached_catalog = {
            "default_model": "dashscope/cached-model",
            "models": [{"id": "dashscope/cached-model"}],
        }
        redis = FakeRedis(json.dumps(cached_catalog).encode())

        with patch.object(
            model_cache,
            "get_async_redis_client",
            return_value=redis,
        ):
            result = await model_cache.get_model_catalog()

        self.assertEqual(cached_catalog, result)
        self.assertEqual(model_cache.MODEL_CATALOG_CACHE_KEY, redis.get_key)
        self.assertIsNone(redis.set_arguments)

    async def test_cache_miss_builds_from_config_and_sets_ttl(self):
        redis = FakeRedis()

        with patch.object(
            model_cache,
            "get_async_redis_client",
            return_value=redis,
        ):
            result = await model_cache.get_model_catalog()

        key, raw_catalog, ttl = redis.set_arguments
        self.assertEqual(model_cache.MODEL_CATALOG_CACHE_KEY, key)
        self.assertEqual(model_cache.MODEL_CATALOG_CACHE_TTL_SECONDS, ttl)
        self.assertEqual(result, json.loads(raw_catalog))

    async def test_redis_failure_falls_back_to_config(self):
        redis = FakeRedis(error=RedisConnectionError("unavailable"))

        with (
            patch.object(
                model_cache,
                "get_async_redis_client",
                return_value=redis,
            ),
            patch.object(model_cache.logger, "warning") as warning,
        ):
            result = await model_cache.get_model_catalog()

        self.assertEqual(model_cache.build_model_catalog(), result)
        warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
