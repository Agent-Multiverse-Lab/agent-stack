"""Settings 管理入口：双供应商模板、保存和凭据脱敏。"""

from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from pydantic import ValidationError

from server.entities.model import ModelSettingsRequest
from server.router.model_router import router
from server.service import model_service as service
from server.utils.auth import get_current_user, is_admin_user
from src.configs import config
from src.database import User, get_db
from test.test_model_repository import SQLiteModelTestCase


class ModelSettingsTest(SQLiteModelTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        refresh = patch.object(
            service,
            "refresh_model_list_cache",
            new_callable=AsyncMock,
            return_value=True,
        )
        refresh.start()
        self.addCleanup(refresh.stop)

    async def test_save_preserves_hidden_parameters_and_key(self):
        await self.insert_provider(
            "dashscope",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            extra_headers={"X-Private": "header-secret"},
            enabled_models=[{"model_id": "qwen3:8b", "model_type": "qwen", "body_overrides": {"temperature": 0.4}}],
        )
        await self.db.commit()
        request = ModelSettingsRequest(
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            models=[{"model_id": "qwen3:8b", "capabilities": ["chat"]}],
        )
        with patch.object(service, "_request_json", new_callable=AsyncMock) as remote:
            await service.save_model_settings(self.db, "dashscope", request)
            remote.assert_not_called()
        saved = await self.repository.get_provider_by_id("dashscope")
        self.assertEqual(saved.api_key, "secret-key")
        self.assertEqual(saved.extra_headers, {"X-Private": "header-secret"})
        self.assertEqual(saved.enabled_models[0]["body_overrides"], {"temperature": 0.4})
        self.assertEqual(saved.enabled_models[0]["capabilities"], ["chat"])
        self.assertFalse(saved.is_enabled)
        cleared = request.model_copy(update={"api_key": ""})
        await service.save_model_settings(self.db, "dashscope", cleared)
        self.assertEqual(saved.api_key, "")

    async def test_details_read_database_and_missing_records_are_not_synthesized(self):
        await service.ensure_builtin_model_providers(self.db)
        template = await service.get_settings_provider(self.db, "deepseek")
        self.assertEqual(template.name, "DeepSeek")
        self.assertEqual(template.base_url, "https://api.deepseek.com/v1")
        self.assertFalse(template.is_enabled)
        self.assertFalse(template.has_api_key)
        self.assertEqual(len(template.enabled_models), 2)
        self.assertIsNotNone(await self.repository.get_provider_by_id("deepseek"))
        with self.assertRaises(LookupError):
            await service.get_settings_provider(self.db, "ollama")
        with self.assertRaises(LookupError):
            await service.save_model_settings(
                self.db,
                "ollama",
                ModelSettingsRequest(base_url="http://localhost:11434/v1"),
            )

    async def test_discovery_uses_draft_without_saving_and_filters_non_chat(self):
        await service.ensure_builtin_model_providers(self.db)
        self.db.commit.reset_mock()
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
            result = await service.discover_settings_models(self.db, "dashscope", request)
        self.assertEqual([m.model_id for m in result], ["chat", "unknown"])
        self.assertEqual(result[0].capabilities, ["chat", "tools"])
        self.assertEqual(result[1].capabilities, [])
        self.assertEqual(remote.call_args.args[0], "http://localhost:8000/v1")
        self.assertEqual(remote.call_args.args[1], {"Authorization": "Bearer draft-secret"})
        self.db.commit.assert_not_called()
        self.assertEqual(len((await self.repository.get_provider_by_id("dashscope")).enabled_models), 4)

    async def test_probe_validates_unsaved_api_key_without_a_selected_model(self):
        await self.insert_provider(
            "dashscope",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            extra_headers={"X-Private": "private"},
        )
        await self.db.commit()
        self.db.commit.reset_mock()
        request = ModelSettingsRequest(base_url="http://localhost:8000/v1", api_key="new-key")
        with patch.object(service, "_request_json", new_callable=AsyncMock, return_value={"data": []}) as remote:
            result = await service.test_settings_connection(self.db, "dashscope", request)
        self.assertTrue(result.success)
        self.assertEqual(remote.call_args.args[0], "http://localhost:8000/v1")
        self.assertNotIn("X-Private", remote.call_args.args[1])
        self.assertEqual(remote.call_args.args[1]["Authorization"], "Bearer new-key")
        self.assertEqual(remote.call_args.args[2], "/models")
        self.assertNotIn("body", remote.call_args.kwargs)
        self.db.commit.assert_not_called()
        self.assertEqual((await self.repository.get_provider_by_id("dashscope")).api_key, "secret-key")

    async def test_probe_reports_rejected_api_key(self):
        await service.ensure_builtin_model_providers(self.db)
        self.db.commit.reset_mock()
        request = ModelSettingsRequest(base_url="https://example.com/v1", api_key="bad-key")
        with patch.object(
            service,
            "_request_json",
            new_callable=AsyncMock,
            side_effect=service.ModelConnectionError("http_error", 401),
        ):
            result = await service.test_settings_connection(
                self.db, "deepseek", request,
            )
        self.assertFalse(result.success)
        self.assertEqual(result.error, "http_error")
        self.assertEqual(result.status_code, 401)
        self.db.commit.assert_not_called()

    async def test_model_routes_are_connected_and_require_authentication(self):
        app = FastAPI()
        app.include_router(router, prefix="/api")

        async def get_test_db():
            return self.db

        app.dependency_overrides[get_db] = get_test_db
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            for method, path in (
                ("GET", "/api/models/providers"),
                ("GET", "/api/models/providers/deepseek"),
                ("POST", "/api/models/providers/deepseek"),
                ("POST", "/api/models/providers/deepseek/discover"),
                ("POST", "/api/models/providers/deepseek/test"),
            ):
                with self.subTest(path=path), patch.object(service, "_request_json", new_callable=AsyncMock) as remote:
                    response = await client.request(method, path)
                    self.assertEqual(response.status_code, 401)
                    remote.assert_not_called()
            response = await client.get("/api/models")
            self.assertEqual(response.status_code, 401)

    async def test_non_admin_can_read_save_discover_and_test_providers(self):
        await service.ensure_builtin_model_providers(self.db)
        user = self.session.get(User, self.user_id)
        app = FastAPI()
        app.include_router(router, prefix="/api")

        async def get_test_user():
            return user

        async def get_test_db():
            return self.db

        app.dependency_overrides[get_current_user] = get_test_user
        app.dependency_overrides[get_db] = get_test_db
        payload = {
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "test-key",
            "is_enabled": True,
            "models": [{"model_id": "deepseek-v4-pro", "capabilities": []}],
        }
        with patch.object(config, "admin_emails", ""), patch.object(
            service,
            "_request_json",
            new_callable=AsyncMock,
            return_value={"data": [{"id": "deepseek-v4-pro"}]},
        ):
            self.assertFalse(is_admin_user(user))
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://test",
            ) as client:
                response = await client.get("/api/models/providers")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.json()), 2)

                response = await client.get("/api/models/providers/deepseek")
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("api_key", response.json())

                response = await client.post("/api/models/providers/deepseek", json=payload)
                self.assertEqual(response.status_code, 200)
                self.assertTrue((await self.repository.get_provider_by_id("deepseek")).is_enabled)

                response = await client.post("/api/models/providers/deepseek/discover", json=payload)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()[0]["model_id"], "deepseek-v4-pro")

                response = await client.post("/api/models/providers/deepseek/test", json=payload)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["success"])

    async def test_null_key_rejected(self):
        with self.assertRaises(ValidationError):
            ModelSettingsRequest(base_url="http://localhost/v1", api_key=None)
