"""纯字段预置、显式校验及全局幂等补齐。"""

from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from server.service import model_service as service
from src.model.providers.builtin import MODEL_PROVIDER_PRESETS, ModelProviderPreset, PresetChatModel
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
            key: deepcopy(getattr(existing, key)) for key in (
                "name", "base_url", "protocol", "api_key", "extra_headers",
                "is_enabled", "enabled_models", "created_at", "updated_at",
            )
        }
        await service.ensure_builtin_model_providers(self.db)
        await service.ensure_builtin_model_providers(self.db)
        self.assertEqual([item.provider_id for item in await self.repository.list_providers()], ["custom", "dashscope", "deepseek"])
        after = await self.repository.get_provider_by_id("deepseek")
        self.assertEqual({key: getattr(after, key) for key in before}, before)
        qwen = await self.repository.get_provider_by_id("dashscope")
        self.assertFalse(qwen.is_enabled)
        self.assertEqual(qwen.api_key, "")
        self.assertEqual(qwen.extra_headers, {})
        self.assertEqual(len(qwen.enabled_models), 4)
        self.assertEqual([item.provider_id for item in await service.list_settings_provider_summaries(self.db)], ["custom", "dashscope", "deepseek"])

    async def test_all_presets_validated_before_first_insert(self):
        original = MODEL_PROVIDER_PRESETS[0]
        invalid_presets = (
            (original, original),
            (original, replace(MODEL_PROVIDER_PRESETS[1], enabled_models=())),
            (original, replace(MODEL_PROVIDER_PRESETS[1], base_url="invalid")),
            (replace(original, is_enabled="false"),),
            (replace(original, enabled_models=(original.enabled_models[0],) * 2),),
            (replace(original, enabled_models=(PresetChatModel(model_id="m", model_type="qwen", capabilities=("chat", "chat")),)),),
            (replace(original, enabled_models=(PresetChatModel(model_id="m", model_type="qwen", body_overrides={"messages": []}),)),),
        )
        for presets in invalid_presets:
            with self.subTest(presets=presets), patch.object(service, "MODEL_PROVIDER_PRESETS", presets):
                with self.assertRaises((ValueError, ValidationError)):
                    await service.ensure_builtin_model_providers(self.db)
        self.db.execute.assert_not_called()
        self.db.commit.assert_not_called()
        self.assertEqual(await self.repository.list_providers(), [])

    async def test_mapping_copies_nested_json_and_leaves_preset_untouched(self):
        body = {"parameters": {"values": [1, 2]}}
        preset = ModelProviderPreset(
            provider_id="custom", name=" Custom ", base_url="https://custom.example/v1/",
            enabled_models=(PresetChatModel(model_id="chat", model_type="qwen", body_overrides=body),),
        )
        with patch.object(service, "MODEL_PROVIDER_PRESETS", (preset,)):
            await service.ensure_builtin_model_providers(self.db)
        saved = await self.repository.get_provider_by_id("custom")
        self.assertEqual((saved.name, saved.base_url), ("Custom", "https://custom.example/v1"))
        self.assertEqual((preset.name, preset.base_url), (" Custom ", "https://custom.example/v1/"))
        body["parameters"]["values"].append(3)
        self.assertEqual(saved.enabled_models[0]["body_overrides"]["parameters"]["values"], [1, 2])
        saved.enabled_models[0]["body_overrides"]["parameters"]["values"].append(4)
        self.assertEqual(body["parameters"]["values"], [1, 2, 3])

    async def test_database_failure_rolls_back_all_presets(self):
        self.db.commit.side_effect = SQLAlchemyError("private database details")
        with self.assertRaisesRegex(RuntimeError, "补齐模型供应商失败") as error:
            await service.ensure_builtin_model_providers(self.db)
        self.assertNotIn("private", str(error.exception))
        self.db.rollback.assert_awaited_once()
        self.assertEqual(await self.repository.list_providers(), [])
