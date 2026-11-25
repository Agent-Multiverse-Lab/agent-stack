"""纯字段预置及全局幂等补齐。"""

from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError

from src.model import service
from src.model.presets import MODEL_PROVIDER_PRESETS, ModelProviderPreset, PresetModel
from test.test_model_repository import SQLiteModelTestCase


class ModelProviderPresetTest(SQLiteModelTestCase):
    async def test_ensure_inserts_once_and_does_not_override_saved_configuration(self):
        existing = await self.insert_provider(
            "deepseek", name="Platform DeepSeek", base_url="https://custom.example/v1",
            extra_headers={"X-Private": "saved-header"},
        )
        await self.insert_provider("custom")
        await self.db.commit()
        before = {
            key: getattr(existing, key) for key in (
                "name", "base_url", "embedding_base_url", "rerank_base_url",
                "protocol", "api_key", "extra_headers",
                "is_enabled", "enabled_models", "created_at", "updated_at",
            )
        }
        await service.ensure_builtin_model_providers(self.db)
        await service.ensure_builtin_model_providers(self.db)
        self.assertEqual(
            [item.provider_id for item in await self.repository.list_model_providers()],
            ["anthropic", "custom", "dashscope", "deepseek", "gemini", "openai"],
        )
        after = await self.repository.get_model_provider_by_id("deepseek")
        self.assertEqual({key: getattr(after, key) for key in before}, before)
        qwen = await self.repository.get_model_provider_by_id("dashscope")
        self.assertFalse(qwen.is_enabled)
        self.assertEqual(qwen.api_key, "DASHSCOPE_API_KEY")
        self.assertEqual(qwen.embedding_base_url, "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.assertEqual(qwen.rerank_base_url, "https://dashscope.aliyuncs.com/compatible-api/v1/reranks")
        self.assertEqual(qwen.extra_headers, {})
        self.assertEqual(len(qwen.enabled_models), 9)
        self.assertEqual(
            [m["category"] for m in qwen.enabled_models],
            ["chat"] * 4 + ["embedding"] * 3 + ["rerank"] * 2,
        )
        openai = await self.repository.get_model_provider_by_id("openai")
        self.assertEqual(openai.embedding_base_url, "https://api.openai.com/v1")
        gemini = await self.repository.get_model_provider_by_id("gemini")
        self.assertEqual(gemini.embedding_base_url, "https://generativelanguage.googleapis.com")
        self.assertEqual(
            [(preset.provider_id, preset.api_key) for preset in MODEL_PROVIDER_PRESETS],
            [
                ("deepseek", "DEEPSEEK_API_KEY"),
                ("dashscope", "DASHSCOPE_API_KEY"),
                ("openai", "OPENAI_API_KEY"),
                ("anthropic", "ANTHROPIC_API_KEY"),
                ("gemini", "GEMINI_API_KEY"),
            ],
        )
        self.assertEqual(
            [item["provider_id"] for item in await service.list_model_providers(self.db)],
            ["anthropic", "custom", "dashscope", "deepseek", "gemini", "openai"],
        )

    async def test_mapping_normalizes_values_and_leaves_preset_untouched(self):
        preset = ModelProviderPreset(
            provider_id="custom", name=" Custom ", base_url="https://custom.example/v1/",
            embedding_base_url="https://embed.example/v1/",
            rerank_base_url="https://rerank.example/v1/",
            enabled_models=(PresetModel(model_id="chat", category="embedding"),),
        )
        with patch.object(service, "MODEL_PROVIDER_PRESETS", (preset,)):
            await service.ensure_builtin_model_providers(self.db)
        saved = await self.repository.get_model_provider_by_id("custom")
        self.assertEqual(
            (saved.name, saved.base_url, saved.embedding_base_url, saved.rerank_base_url),
            ("Custom", "https://custom.example/v1", "https://embed.example/v1", "https://rerank.example/v1"),
        )
        self.assertEqual(saved.enabled_models[0]["category"], "embedding")
        self.assertEqual((preset.name, preset.base_url), (" Custom ", "https://custom.example/v1/"))

    async def test_database_failure_rolls_back_all_presets(self):
        self.db.commit.side_effect = SQLAlchemyError("private database details")
        with self.assertRaisesRegex(RuntimeError, "补齐模型供应商失败") as error:
            await service.ensure_builtin_model_providers(self.db)
        self.assertNotIn("private", str(error.exception))
        self.db.rollback.assert_awaited_once()
        self.assertEqual(await self.repository.list_model_providers(), [])
