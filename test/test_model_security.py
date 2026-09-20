"""模型凭据转发、HTTPS、数据库密文与公网出站边界。"""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from pydantic import SecretStr
from sqlalchemy import text

from server.entities.model import ModelProviderCreate, ModelSettingsRequest
from server.service import model_service as service
from server.service.model_outbound import UnsafeModelTarget, resolve_public_target
from src.configs import config
from src.database.credential_types import decrypt_credential
from test.test_model_repository import SQLiteModelTestCase


class ModelCredentialSecurityTest(SQLiteModelTestCase):
    async def test_new_url_cannot_reuse_saved_credentials(self):
        await self.insert_provider("deepseek", extra_headers={"X-Private": "private-header"})
        await self.db.commit()
        draft = ModelSettingsRequest(base_url="https://new.example/v1", models=[{"model_id": "chat"}])
        with patch.object(service, "_request_json", new_callable=AsyncMock) as remote:
            for method in (service.save_model_settings, service.discover_settings_models, service.test_settings_connection):
                with self.assertRaises(ValueError):
                    await method(self.db, self.user_id, "deepseek", draft)
            remote.assert_not_called()
        explicit = ModelSettingsRequest(base_url="https://new.example/v1", api_key="new-key", models=[{"model_id": "chat"}])
        with patch.object(service, "_request_json", new_callable=AsyncMock, return_value={"data": []}) as remote:
            await service.discover_settings_models(self.db, self.user_id, "deepseek", explicit)
            self.assertEqual(remote.call_args.args[1], {"Authorization": "Bearer new-key"})
        original = await self.repository.get_provider_by_id("deepseek")
        self.assertEqual(original.api_key, "secret-key")
        self.assertEqual(original.extra_headers, {"X-Private": "private-header"})

    async def test_raw_database_contains_ciphertext_not_secrets(self):
        await self.insert_provider("deepseek", extra_headers={"X-Private": "private-header"})
        await self.db.commit()
        raw = self.session.execute(text("SELECT api_key,extra_headers FROM model_provider")).one()
        self.assertNotIn("secret-key", str(raw))
        self.assertNotIn("private-header", str(raw))
        self.assertTrue(raw[0].startswith("enc:v1:"))
        self.assertEqual(decrypt_credential(raw[0]), "secret-key")
        with self.assertRaises(RuntimeError):
            decrypt_credential("plain-key")
        with patch.object(config, "model_credential_key", SecretStr("")):
            with self.assertRaises(RuntimeError):
                decrypt_credential(raw[0])

    async def test_missing_cipher_key_fails_without_committing_plaintext(self):
        with patch.object(config, "model_credential_key", SecretStr("")):
            with self.assertRaises(RuntimeError):
                await service.create_provider(self.db, self.user_id, ModelProviderCreate(provider_id="deepseek", name="DeepSeek", base_url="https://example.com/v1", api_key="must-not-persist"))
        self.assertEqual(self.session.execute(text("SELECT count(*) FROM model_provider")).scalar_one(), 0)

class ModelOutboundSecurityTest(unittest.IsolatedAsyncioTestCase):
    async def test_internal_literal_addresses_are_blocked_before_http(self):
        for host in ("127.0.0.1", "10.0.0.1", "172.16.0.1", "192.168.0.1", "169.254.169.254", "100.100.100.200", "0.0.0.0", "[::1]", "[fc00::1]", "[fe80::1]", "[::ffff:127.0.0.1]", "[64:ff9b::a00:1]", "localhost", "host.internal"):
            with self.subTest(host=host), patch.object(service.httpx, "AsyncClient") as client:
                with self.assertRaises(service.ModelConnectionError) as failure:
                    await service._request_json(f"https://{host}/v1", {"Authorization": "Bearer private"}, "/models")
                self.assertEqual(failure.exception.code, "blocked_target")
                client.assert_not_called()

    async def test_dns_all_answers_checked_and_pinned(self):
        loop = asyncio.get_running_loop()
        public = (2, 1, 6, "", ("93.184.216.34", 443))
        private = (10, 1, 6, "", ("::1", 443, 0, 0))
        with patch.object(loop, "getaddrinfo", new_callable=AsyncMock, return_value=[public, private]):
            with self.assertRaises(UnsafeModelTarget):
                await resolve_public_target("https://models.example/v1")
        with patch.object(loop, "getaddrinfo", new_callable=AsyncMock, return_value=[public]) as dns:
            target, authority, hostname = await resolve_public_target("https://models.example/v1")
            self.assertEqual(str(target), "https://93.184.216.34/v1")
            self.assertEqual((authority, hostname), ("models.example", "models.example"))
            dns.assert_awaited_once()

    async def test_https_host_sni_no_proxy_and_no_redirect(self):
        original_client = httpx.AsyncClient
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(302, headers={"Location": "http://127.0.0.1/secrets"})

        with (
            patch.object(service, "resolve_public_target", new_callable=AsyncMock, return_value=(httpx.URL("https://93.184.216.34/v1"), "models.example", "models.example")),
            patch.object(service.httpx, "AsyncClient", side_effect=lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs)) as client,
        ):
            with self.assertRaises(service.ModelConnectionError):
                await service._request_json("https://models.example/v1", {}, "/models")
            self.assertFalse(client.call_args.kwargs["trust_env"])
            self.assertFalse(client.call_args.kwargs["follow_redirects"])
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].url.host, "93.184.216.34")
        self.assertEqual(seen[0].headers["Host"], "models.example")
        self.assertEqual(seen[0].extensions["sni_hostname"], "models.example")
