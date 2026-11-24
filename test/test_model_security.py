"""模型凭据转发与数据库密文边界。"""

from unittest.mock import AsyncMock, patch

from pydantic import SecretStr
from sqlalchemy import text

from src.configs import config
from src.model import service
from test.test_model_repository import SQLiteModelTestCase


class ModelCredentialSecurityTest(SQLiteModelTestCase):
    async def test_new_url_cannot_reuse_saved_credentials(self):
        await self.insert_provider("deepseek", extra_headers={"X-Private": "private-header"})
        await self.db.commit()
        for url_patch in (
            {"base_url": "https://new.example/v1"},
            {"base_url": "http://localhost:11434/v1", "embedding_base_url": "https://embed.example/v1"},
            {"base_url": "http://localhost:11434/v1", "rerank_base_url": "https://rerank.example/v1"},
        ):
            with self.subTest(url_patch=url_patch), patch.object(service, "_request_json", new_callable=AsyncMock) as remote:
                for method in (service.save_model_settings, service.discover_settings_models, service.test_settings_connection):
                    with self.assertRaises(ValueError):
                        await method(self.db, "deepseek", models=[{"model_id": "chat"}], **url_patch)
                remote.assert_not_called()

        with patch.object(service, "_request_json", new_callable=AsyncMock, return_value={"data": []}) as remote:
            await service.discover_settings_models(
                self.db,
                "deepseek",
                base_url="https://new.example/v1",
                api_key="new-key",
                api_key_provided=True,
                models=[{"model_id": "chat"}],
            )
            self.assertEqual(remote.call_args.args[0], "https://new.example/v1")
            self.assertEqual(remote.call_args.args[1], {"Authorization": "Bearer new-key"})
        original = await self.repository.get_model_provider_by_id("deepseek")
        self.assertEqual(original.api_key, "secret-key")
        self.assertEqual(original.extra_headers, {"X-Private": "private-header"})

    async def test_provider_credentials_stored_as_plaintext_without_cipher_key(self):
        with patch.object(config, "model_credential_key", SecretStr("")):
            await service.create_model_provider(
                self.db,
                provider_id="deepseek",
                name="DeepSeek",
                base_url="https://example.com/v1",
                api_key="sk-plaintext",
                extra_headers={"X-Private": "header-plaintext"},
            )
        raw = self.session.execute(text("SELECT api_key,extra_headers FROM model_provider")).one()
        self.assertEqual(raw[0], "sk-plaintext")
        self.assertIn("header-plaintext", raw[1])
