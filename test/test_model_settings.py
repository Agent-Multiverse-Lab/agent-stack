"""Settings 管理入口：内置供应商模板、保存和凭据脱敏。"""

import os
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI

from server.router.model_router import router
from server.utils.auth import get_current_user, is_admin_user
from src.configs import config
from src.database import User, get_db
from src.model import service
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

    async def test_save_preserves_hidden_parameters_and_key_and_updates_category_urls(self):
        await self.insert_provider(
            "dashscope",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            embedding_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            rerank_base_url="https://dashscope.aliyuncs.com/compatible-api/v1/reranks",
            extra_headers={"X-Private": "header-secret"},
            enabled_models=[
                {
                    "model_id": "qwen3-rerank",
                    "category": "rerank",
                }
            ],
        )
        await self.db.commit()
        with patch.object(service, "_request_json", new_callable=AsyncMock) as remote:
            await service.update_model_provider(
                self.db,
                "dashscope",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                embedding_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                rerank_base_url="https://dashscope.aliyuncs.com/compatible-api/v1/reranks",
                models=[{"model_id": "qwen3-rerank", "category": "rerank", "capabilities": ["chat"]}],
            )
            remote.assert_not_called()
        saved = await self.repository.get_model_provider_by_id("dashscope")
        self.assertEqual(saved.api_key, "secret-key")
        self.assertEqual(saved.extra_headers, {"X-Private": "header-secret"})
        self.assertEqual(saved.enabled_models[0]["category"], "rerank")
        self.assertEqual(saved.enabled_models[0]["capabilities"], ["chat"])
        self.assertEqual(saved.embedding_base_url, "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.assertEqual(saved.rerank_base_url, "https://dashscope.aliyuncs.com/compatible-api/v1/reranks")
        self.assertFalse(saved.is_enabled)
        await service.update_model_provider(
            self.db,
            "dashscope",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            embedding_base_url="https://embed.example/v1",
            rerank_base_url="https://rerank.example/v1/reranks",
            models=[{"model_id": "qwen3-rerank", "category": "rerank", "capabilities": ["chat"]}],
            api_key="",
            api_key_provided=True,
        )
        self.assertEqual(saved.api_key, "")
        self.assertEqual(saved.embedding_base_url, "https://embed.example/v1")
        self.assertEqual(saved.rerank_base_url, "https://rerank.example/v1/reranks")

    async def test_details_read_database_and_missing_records_are_not_synthesized(self):
        await service.ensure_builtin_model_providers(self.db)
        clean_env = {key: value for key, value in os.environ.items() if key != "DEEPSEEK_API_KEY"}
        with patch.dict(os.environ, clean_env, clear=True), patch.object(config, "deepseek_api_key", ""):
            template = await service.get_model_provider(self.db, "deepseek")
        self.assertEqual(template["name"], "DeepSeek")
        self.assertEqual(template["base_url"], "https://api.deepseek.com/v1")
        self.assertNotIn("api_key", template)
        self.assertFalse(template["is_enabled"])
        self.assertFalse(template["has_api_key"])
        self.assertEqual(len(template["models"]), 2)
        self.assertIsNotNone(await self.repository.get_model_provider_by_id("deepseek"))
        with self.assertRaises(LookupError):
            await service.get_model_provider(self.db, "ollama")
        with self.assertRaises(LookupError):
            await service.update_model_provider(
                self.db,
                "ollama",
                base_url="http://localhost:11434/v1",
            )

    async def test_discovery_uses_draft_without_saving_and_filters_non_chat(self):
        await service.ensure_builtin_model_providers(self.db)
        self.db.commit.reset_mock()
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
            result = await service.discover_provider_models(
                self.db,
                "dashscope",
                base_url="http://localhost:8000/v1",
                api_key="draft-secret",
                api_key_provided=True,
            )
        self.assertEqual([m["model_id"] for m in result], ["chat", "unknown"])
        self.assertEqual(result[0]["capabilities"], ["chat", "tools"])
        self.assertEqual(result[1]["capabilities"], [])
        self.assertEqual(remote.call_args.args[0], "http://localhost:8000/v1")
        self.assertEqual(remote.call_args.args[1], {"Authorization": "Bearer draft-secret"})
        self.db.commit.assert_not_called()
        self.assertEqual(len((await self.repository.get_model_provider_by_id("dashscope")).enabled_models), 9)

    async def test_probe_validates_unsaved_api_key_without_a_selected_model(self):
        await self.insert_provider(
            "dashscope",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            extra_headers={"X-Private": "private"},
        )
        await self.db.commit()
        self.db.commit.reset_mock()
        with patch.object(service, "_request_json", new_callable=AsyncMock, return_value={"data": []}) as remote:
            result = await service.test_provider_connection(
                self.db,
                "dashscope",
                base_url="http://localhost:8000/v1",
                api_key="new-key",
                api_key_provided=True,
            )
        self.assertTrue(result["success"])
        self.assertEqual(remote.call_args.args[0], "http://localhost:8000/v1")
        self.assertNotIn("X-Private", remote.call_args.args[1])
        self.assertEqual(remote.call_args.args[1]["Authorization"], "Bearer new-key")
        self.assertEqual(remote.call_args.args[2], "/models")
        self.assertNotIn("body", remote.call_args.kwargs)
        self.db.commit.assert_not_called()
        self.assertEqual((await self.repository.get_model_provider_by_id("dashscope")).api_key, "secret-key")

    async def test_probe_reports_rejected_api_key(self):
        await service.ensure_builtin_model_providers(self.db)
        self.db.commit.reset_mock()
        with patch.object(
            service,
            "_request_json",
            new_callable=AsyncMock,
            side_effect=service.ModelConnectionError("http_error", 401),
        ):
            result = await service.test_provider_connection(
                self.db,
                "deepseek",
                base_url="https://example.com/v1",
                api_key="bad-key",
                api_key_provided=True,
            )
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "http_error")
        self.assertEqual(result["status_code"], 401)
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
                ("POST", "/api/models/providers"),
                ("GET", "/api/models/providers/deepseek"),
                ("POST", "/api/models/providers/deepseek"),
                ("PUT", "/api/models/providers/deepseek"),
                ("DELETE", "/api/models/providers/deepseek"),
                ("POST", "/api/models/providers/deepseek/discover"),
                ("POST", "/api/models/providers/deepseek/test"),
            ):
                with self.subTest(path=path), patch.object(service, "_request_json", new_callable=AsyncMock) as remote:
                    response = await client.request(method, path)
                    self.assertEqual(response.status_code, 401)
                    remote.assert_not_called()
            response = await client.get("/api/models")
            self.assertEqual(response.status_code, 401)

    async def test_non_admin_can_read_save_discover_and_test_providers_without_key_leak(self):
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
            "embedding_base_url": "",
            "rerank_base_url": "",
            "api_key": "test-key",
            "is_enabled": True,
            "models": [{"model_id": "deepseek-v4-pro", "category": "chat", "capabilities": []}],
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
                providers_envelope = response.json()
                self.assertEqual(providers_envelope["status"], "success")
                self.assertEqual(len(providers_envelope["data"]), 5)
                for item in providers_envelope["data"]:
                    self.assertNotIn("api_key", item)

                response = await client.get("/api/models/providers/deepseek")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["status"], "success")
                body = response.json()["data"]
                self.assertNotIn("api_key", body)
                self.assertEqual(body["base_url"], "https://api.deepseek.com/v1")
                self.assertEqual(body["embedding_base_url"], "")
                self.assertEqual(body["rerank_base_url"], "")
                self.assertEqual(len(body["models"]), 2)

                response = await client.post("/api/models/providers/deepseek", json=payload)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["status"], "success")
                self.assertTrue((await self.repository.get_model_provider_by_id("deepseek")).is_enabled)

                with patch.object(service, "get_async_redis_client", side_effect=OSError("no redis")):
                    catalog_resp = await client.get("/api/models?category=chat")
                self.assertEqual(catalog_resp.status_code, 200)
                catalog_body = catalog_resp.json()
                self.assertEqual(catalog_body["status"], "success")
                self.assertEqual(catalog_body["data"]["deepseek"]["provider_id"], "deepseek")
                self.assertEqual(catalog_body["data"]["deepseek"]["display_name"], "DeepSeek")
                self.assertEqual(
                    catalog_body["data"]["deepseek"]["models"],
                    [{"model_id": "deepseek-v4-pro", "category": "chat", "capabilities": []}],
                )
                self.assertNotIn("default_model", catalog_body["data"])

                response = await client.post("/api/models/providers/deepseek/discover", json=payload)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["status"], "success")
                self.assertEqual(response.json()["data"][0]["model_id"], "deepseek-v4-pro")

                response = await client.post("/api/models/providers/deepseek/test", json=payload)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["status"], "success")
                self.assertTrue(response.json()["data"]["success"])

                create_payload = {
                    "provider_id": "custom_claude",
                    "name": "Custom Claude",
                    "protocol": "anthropic",
                    "base_url": "https://api.anthropic.com",
                    "api_key": "sk-ant-123",
                    "is_enabled": True,
                    "models": [{"model_id": "claude-sonnet-5-5", "category": "chat", "capabilities": []}],
                }
                created = await client.post("/api/models/providers", json=create_payload)
                self.assertEqual(created.status_code, 201)
                self.assertEqual(created.json()["status"], "success")
                self.assertEqual(created.json()["data"]["provider_id"], "custom_claude")

                detail = await client.get("/api/models/providers/custom_claude")
                self.assertEqual(detail.status_code, 200)
                self.assertEqual(detail.json()["status"], "success")
                detail_data = detail.json()["data"]
                self.assertEqual(detail_data["protocol"], "anthropic")
                self.assertNotIn("api_key", detail_data)
                self.assertTrue(detail_data["has_api_key"])

                dup = await client.post("/api/models/providers", json=create_payload)
                self.assertEqual(dup.status_code, 409)

                for bad_payload in (
                    {**create_payload, "provider_id": "bad/id"},
                    {**create_payload, "provider_id": "ok_id", "name": "  "},
                    {**create_payload, "provider_id": "ok_id", "base_url": ""},
                    {**create_payload, "provider_id": "ok_id", "protocol": "unknown"},
                ):
                    bad_resp = await client.post("/api/models/providers", json=bad_payload)
                    self.assertEqual(bad_resp.status_code, 422)

                # PUT 更新时不传 name/protocol/api_key，应保留库内原值
                put_resp = await client.put(
                    "/api/models/providers/custom_claude",
                    json={
                        "base_url": "https://api.anthropic.com",
                        "is_enabled": False,
                        "models": [{"model_id": "claude-opus-5-5", "category": "chat", "capabilities": []}],
                    },
                )
                self.assertEqual(put_resp.status_code, 200)
                updated_row = await self.repository.get_model_provider_by_id("custom_claude")
                self.assertEqual(updated_row.protocol, "anthropic")
                self.assertEqual(updated_row.name, "Custom Claude")
                self.assertEqual(updated_row.api_key, "sk-ant-123")
                self.assertFalse(updated_row.is_enabled)

                missing_put = await client.put(
                    "/api/models/providers/missing",
                    json={"base_url": "https://example.com/v1"},
                )
                self.assertEqual(missing_put.status_code, 404)

                del_resp = await client.delete("/api/models/providers/custom_claude")
                self.assertEqual(del_resp.status_code, 200)
                self.assertEqual((await client.get("/api/models/providers/custom_claude")).status_code, 404)
                self.assertEqual((await client.delete("/api/models/providers/custom_claude")).status_code, 404)

    async def test_null_key_rejected(self):
        await self.insert_provider("deepseek")
        await self.db.commit()
        with self.assertRaises(ValueError):
            await service.update_model_provider(
                self.db,
                "deepseek",
                base_url="http://localhost/v1",
                api_key=None,
                api_key_provided=True,
            )
