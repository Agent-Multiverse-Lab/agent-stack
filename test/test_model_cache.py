"""PostgreSQL 模型目录投影与 Redis read-through cache 测试。"""

import json
from unittest.mock import patch

from redis.exceptions import ConnectionError as RedisConnectionError

from src.model import service
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
                {"model_id": "qwen3.8-max", "category": "chat", "capabilities": ["tools"]},
                {"model_id": "text-embedding-v4", "category": "embedding", "capabilities": []},
                {"model_id": "qwen3-rerank", "category": "rerank", "capabilities": []},
            ],
        )
        await self.insert_provider(
            "disabled",
            name="Disabled",
            is_enabled=False,
            enabled_models=[
                {"model_id": "hidden", "category": "chat", "capabilities": []},
            ],
        )
        await self.db.commit()

    async def test_builds_grouped_catalog_from_enabled_database_providers(self):
        catalog = await service.build_model_catalog(self.db, category="chat")
        self.assertEqual(list(catalog.keys()), ["dashscope"])
        self.assertEqual(catalog["dashscope"]["provider_id"], "dashscope")
        self.assertEqual(catalog["dashscope"]["display_name"], "Qwen")
        self.assertEqual(
            catalog["dashscope"]["models"],
            [{"model_id": "qwen3.8-max", "category": "chat", "capabilities": ["tools"]}],
        )
        self.assertNotIn("id", catalog["dashscope"]["models"][0])
        self.assertNotIn("default_model", catalog)

        embedding_catalog = await service.build_model_catalog(self.db, category="embedding")
        self.assertEqual(
            embedding_catalog["dashscope"]["models"],
            [{"model_id": "text-embedding-v4", "category": "embedding", "capabilities": []}],
        )

    async def test_cache_hit_returns_filtered_catalog_without_rewrite(self):
        cached_catalog = {
            "dashscope": {
                "provider_id": "dashscope",
                "display_name": "Qwen",
                "models": [
                    {"model_id": "cached-chat", "category": "chat", "capabilities": []},
                    {"model_id": "cached-emb", "category": "embedding", "capabilities": []},
                ],
            }
        }
        redis = FakeRedis(json.dumps(cached_catalog).encode())

        with patch.object(service, "get_async_redis_client", return_value=redis):
            chat_result = await service.list_models(self.db, category="chat")
            emb_result = await service.list_models(self.db, category="embedding")

        self.assertEqual(chat_result["dashscope"]["models"][0]["model_id"], "cached-chat")
        self.assertEqual(len(chat_result["dashscope"]["models"]), 1)
        self.assertEqual(emb_result["dashscope"]["models"][0]["model_id"], "cached-emb")
        self.assertEqual(service.MODEL_CATALOG_CACHE_KEY, redis.get_key)
        self.assertIsNone(redis.set_arguments)

    async def test_cache_miss_builds_full_catalog_and_sets_ttl(self):
        redis = FakeRedis()

        with patch.object(service, "get_async_redis_client", return_value=redis):
            result = await service.list_models(self.db, category="chat")

        key, raw_catalog, ttl = redis.set_arguments
        self.assertEqual(service.MODEL_CATALOG_CACHE_KEY, key)
        self.assertEqual(service.MODEL_LIST_CACHE_TTL_SECONDS, ttl)
        stored = json.loads(raw_catalog)
        self.assertEqual(len(stored["dashscope"]["models"]), 3)
        self.assertEqual(len(result["dashscope"]["models"]), 1)
        self.assertEqual(result["dashscope"]["models"][0]["model_id"], "qwen3.8-max")

    async def test_invalid_cache_and_redis_failure_fall_back_to_database(self):
        for redis in (
            FakeRedis(b'{"dashscope":{"models":[{"id":"incomplete"}]}}'),
            FakeRedis(error=RedisConnectionError("unavailable")),
        ):
            with self.subTest(redis=redis), patch.object(
                service,
                "get_async_redis_client",
                return_value=redis,
            ):
                result = await service.list_models(self.db, category="chat")

            self.assertEqual(
                ["qwen3.8-max"],
                [item["model_id"] for item in result["dashscope"]["models"]],
            )
