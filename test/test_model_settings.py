"""Settings 管理入口：不丢失私有配置，临时探测不写库，错误不泄露密钥。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from pydantic import ValidationError

from server.entities.model import ModelSettingsRequest
from server.router.model_router import router
from server.service import model_service as service
from server.utils.auth import get_current_user
from src.database import get_db
from test.test_model_repository import SQLiteModelTestCase


class ModelSettingsTest(SQLiteModelTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.cache = patch.object(service, "rebuild_model_cache", new_callable=AsyncMock, return_value=True)
        self.cache.start()
        self.addCleanup(self.cache.stop)

    async def test_save_preserves_hidden_parameters_and_key(self):
        await self.insert_provider(
            "ollama",
            extra_headers={"X-Private": "header-secret"},
            enabled_models=[{"model_id": "qwen3:8b", "model_type": "ollama", "body_overrides": {"temperature": 0.4}}],
        )
        await self.db.commit()
        request = ModelSettingsRequest(base_url="http://localhost:11434/v1", models=[{"model_id": "qwen3:8b", "capabilities": ["chat"]}])
        await service.save_model_settings(self.db, self.user_id, "ollama", request)
        saved = await self.repository.get_provider_by_id("ollama")
        self.assertEqual(saved.api_key, "secret-key")
        self.assertEqual(saved.extra_headers, {"X-Private": "header-secret"})
        self.assertEqual(saved.enabled_models[0]["body_overrides"], {"temperature": 0.4})
        self.assertEqual(saved.enabled_models[0]["capabilities"], ["chat"])
        self.assertFalse(saved.is_enabled)
        cleared = request.model_copy(update={"api_key": ""})
        await service.save_model_settings(self.db, self.user_id, "ollama", cleared)
        self.assertEqual(saved.api_key, "")

    async def test_discovery_uses_draft_without_saving_and_filters_non_chat(self):
        request = ModelSettingsRequest(base_url="http://localhost:8000/v1", api_key="draft-secret")
        with patch.object(
            service,
            "_request_json",
            new_callable=AsyncMock,
            return_value={
                "data": [
                    {"id": "chat", "capabilities": {"chat": True, "vision": False, "tools": True}},
                    {"id": "unknown"},
                    {"id": "embed", "type": "embedding"},
                ]
            },
        ) as remote:
            result = await service.discover_settings_models(self.db, self.user_id, "vllm", request)
        self.assertEqual([m.model_id for m in result], ["chat", "unknown"])
        self.assertEqual(result[0].capabilities, ["chat", "tools"])
        self.assertEqual(result[1].capabilities, [])
        self.assertEqual(remote.call_args.args[1], {"Authorization": "Bearer draft-secret"})
        self.db.commit.assert_not_called()
        self.assertIsNone(await self.repository.get_provider_by_id("vllm"))

    async def test_probe_validates_unsaved_api_key_without_a_selected_model(self):
        await self.insert_provider("ollama", extra_headers={"X-Private": "private"})
        await self.db.commit()
        self.db.commit.reset_mock()
        request = ModelSettingsRequest(base_url="http://localhost:8000/v1", api_key="new-key")
        with patch.object(service, "_request_json", new_callable=AsyncMock, return_value={"data": []}) as remote:
            result = await service.test_settings_connection(self.db, self.user_id, "ollama", request)
        self.assertTrue(result.success)
        self.assertEqual(remote.call_args.args[0], "http://localhost:8000/v1")
        self.assertNotIn("X-Private", remote.call_args.args[1])
        self.assertEqual(remote.call_args.args[1]["Authorization"], "Bearer new-key")
        self.assertEqual(remote.call_args.args[2], "/models")
        self.assertNotIn("body", remote.call_args.kwargs)
        self.db.commit.assert_not_called()
        self.assertEqual((await self.repository.get_provider_by_id("ollama")).api_key, "secret-key")

    async def test_probe_reports_rejected_api_key(self):
        request = ModelSettingsRequest(base_url="https://example.com/v1", api_key="bad-key")
        with patch.object(
            service,
            "_request_json",
            new_callable=AsyncMock,
            side_effect=service.ModelConnectionError("http_error", 401),
        ):
            result = await service.test_settings_connection(
                self.db, self.user_id, "deepseek", request,
            )
        self.assertFalse(result.success)
        self.assertEqual(result.error, "http_error")
        self.assertEqual(result.status_code, 401)
        self.db.commit.assert_not_called()

    async def test_authenticated_api_and_redacted_validation(self):
        app = FastAPI()
        app.include_router(router, prefix="/api")

        async def override_db():
            return self.db

        async def override_user():
            return SimpleNamespace(id=self.user_id)

        app.dependency_overrides[get_db] = override_db
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            response = await client.get("/api/models/providers")
            self.assertEqual(response.status_code, 401)
            app.dependency_overrides[get_current_user] = override_user
            response = await client.post("/api/models/providers/deepseek", json={"base_url": "invalid", "api_key": "private-secret"})
            self.assertEqual(response.status_code, 422)
            self.assertNotIn("private-secret", response.text)
            response = await client.post("/api/models/providers/deepseek", json={"base_url": "http://localhost/v1", "api_key": "private-secret"})
            self.assertEqual(response.status_code, 200)
            response = await client.get("/api/models/providers")
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("private-secret", response.text)
            self.assertTrue(response.json()[0]["has_api_key"])

    async def test_null_key_rejected(self):
        with self.assertRaises(ValidationError):
            ModelSettingsRequest(base_url="http://localhost/v1", api_key=None)
