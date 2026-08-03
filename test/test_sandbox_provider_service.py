from __future__ import annotations

import importlib
import sys
import threading
import time
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

import httpx

_SANDBOX_PACKAGE = "_sandbox_provider_test_package"
_SANDBOX_ROOT = (
    Path(__file__).resolve().parents[1] / "src" / "agents" / "backends" / "sandbox"
)
_package = types.ModuleType(_SANDBOX_PACKAGE)
_package.__path__ = [str(_SANDBOX_ROOT)]
sys.modules.setdefault(_SANDBOX_PACKAGE, _package)

_provision_client = importlib.import_module(f"{_SANDBOX_PACKAGE}.provision_client")
_provider_service = importlib.import_module(f"{_SANDBOX_PACKAGE}.provider_service")
SandboxProvision = _provision_client.SandboxProvision
SandboxProvisionClient = _provision_client.SandboxProvisionClient
SandboxProviderService = _provider_service.SandboxProviderService


class FakeProvisionClient:
    def __init__(self, *, create_delay: float = 0) -> None:
        self._lock = threading.Lock()
        self._provisions: dict[str, SandboxProvision] = {}
        self.create_delay = create_delay
        self.create_calls = 0
        self.delete_calls: list[str] = []
        self.close_calls = 0

    def get(self, sandbox_id: str) -> SandboxProvision | None:
        with self._lock:
            return self._provisions.get(sandbox_id)

    def create(
        self,
        *,
        sandbox_id: str,
        thread_id: str,
        user_id: str,
        **_kwargs: object,
    ) -> SandboxProvision:
        _ = (thread_id, user_id)
        if self.create_delay:
            time.sleep(self.create_delay)
        provision = SandboxProvision(
            sandbox_id=sandbox_id,
            sandbox_url=f"http://sandbox/{sandbox_id}",
            status="running",
        )
        with self._lock:
            self.create_calls += 1
            self._provisions[sandbox_id] = provision
        return provision

    def delete(self, sandbox_id: str) -> bool:
        with self._lock:
            self.delete_calls.append(sandbox_id)
            self._provisions.pop(sandbox_id, None)
        return True

    def close(self) -> None:
        self.close_calls += 1


class FakeSandbox:
    def __init__(self, **kwargs: object) -> None:
        self.id = kwargs["sandbox_id"]
        self.sandbox_url = kwargs["sandbox_url"]


def fake_sandbox_factory(**kwargs: object) -> FakeSandbox:
    return FakeSandbox(**kwargs)


class SandboxProvisionClientTest(unittest.TestCase):
    def test_lifecycle_requests_match_provisioner_api(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.method == "POST" and request.url.path == "/api/sandboxes":
                return httpx.Response(
                    200,
                    json={
                        "sandbox_id": "sandbox-1",
                        "sandbox_url": "http://sandbox-1",
                        "status": "running",
                    },
                )
            if request.method == "POST" and request.url.path.endswith("/touch"):
                return httpx.Response(200, json={"ok": True})
            if request.method == "DELETE":
                return httpx.Response(200, json={"ok": True})
            return httpx.Response(404, json={"detail": "not found"})

        http_client = httpx.Client(
            base_url="http://provisioner",
            transport=httpx.MockTransport(handler),
        )
        self.addCleanup(http_client.close)
        client = SandboxProvisionClient(
            base_url="http://provisioner",
            http_client=http_client,
        )

        provision = client.create(
            sandbox_id="sandbox-1",
            thread_id="thread-1",
            user_id="user-1",
        )

        self.assertEqual(provision.sandbox_id, "sandbox-1")
        self.assertTrue(client.touch("sandbox-1"))
        self.assertTrue(client.delete("sandbox-1"))
        self.assertEqual(
            [(request.method, request.url.path) for request in requests],
            [
                ("POST", "/api/sandboxes"),
                ("POST", "/api/sandboxes/sandbox-1/touch"),
                ("DELETE", "/api/sandboxes/sandbox-1"),
            ],
        )

    def test_sandbox_id_is_fully_path_encoded(self) -> None:
        self.assertEqual(
            SandboxProvisionClient._sandbox_path("user/thread"),
            "/api/sandboxes/user%2Fthread",
        )


class SandboxProviderSingletonTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await _provider_service.shutdown_sandbox_provider()

    async def asyncTearDown(self) -> None:
        await _provider_service.shutdown_sandbox_provider()

    async def test_init_uses_config_and_get_returns_same_instance(self) -> None:
        with (
            mock.patch.object(
                _provider_service.config,
                "sandbox_provisioner_url",
                "http://provisioner",
            ),
            mock.patch.object(
                _provider_service,
                "SandboxProvisionClient",
            ) as client_class,
        ):
            first = _provider_service.init_sandbox_provider()
            second = _provider_service.init_sandbox_provider()

        client_class.assert_called_once_with("http://provisioner")
        self.assertIs(first, second)
        self.assertIs(first, _provider_service.get_sandbox_provider())

        await _provider_service.shutdown_sandbox_provider()

        client_class.return_value.close.assert_called_once_with()
        with self.assertRaisesRegex(RuntimeError, "尚未初始化"):
            _provider_service.get_sandbox_provider()


class SandboxProviderServiceTest(unittest.TestCase):
    @staticmethod
    def _create_provider(client: FakeProvisionClient) -> SandboxProviderService:
        with (
            mock.patch.object(
                _provider_service,
                "SandboxProvisionClient",
                return_value=client,
            ),
            mock.patch.object(
                _provider_service,
                "_create_custom_sandbox",
                side_effect=fake_sandbox_factory,
            ),
        ):
            return SandboxProviderService()

    def test_acquire_reuses_remote_and_local_sandbox(self) -> None:
        client = FakeProvisionClient()
        provider = self._create_provider(client)

        first_id = provider.acquire("user-1", "thread-1")
        first_sandbox = provider.get(first_id)
        second_id = provider.acquire("user-1", "thread-1")

        self.assertEqual(first_id, second_id)
        self.assertIs(first_sandbox, provider.get(second_id))
        self.assertEqual(client.create_calls, 1)

        self.assertTrue(provider.release(first_id))
        self.assertIsNone(provider.get(first_id))
        self.assertEqual(client.delete_calls, [])

        reacquired_id = provider.acquire("user-1", "thread-1")
        self.assertEqual(reacquired_id, first_id)
        self.assertEqual(client.create_calls, 1)
        self.assertIsNotNone(provider.get(reacquired_id))

    def test_concurrent_acquire_for_same_thread_creates_once(self) -> None:
        client = FakeProvisionClient(create_delay=0.05)
        provider = self._create_provider(client)

        with ThreadPoolExecutor(max_workers=8) as executor:
            sandbox_ids = list(
                executor.map(
                    lambda _index: provider.acquire("user-1", "thread-1"),
                    range(8),
                )
            )

        self.assertEqual(len(set(sandbox_ids)), 1)
        self.assertEqual(client.create_calls, 1)

    def test_destroy_deletes_remote_and_local_state(self) -> None:
        client = FakeProvisionClient()
        provider = self._create_provider(client)
        sandbox_id = provider.acquire("user-1", "thread-1")

        self.assertTrue(provider.destroy(sandbox_id))
        self.assertEqual(client.delete_calls, [sandbox_id])
        self.assertIsNone(provider.get(sandbox_id))

    def test_shutdown_is_idempotent_and_rejects_new_acquire(self) -> None:
        client = FakeProvisionClient()
        provider = self._create_provider(client)
        provider.acquire("user-1", "thread-1")

        provider.shutdown()
        provider.shutdown()

        self.assertEqual(client.close_calls, 1)
        with self.assertRaisesRegex(RuntimeError, "shut down"):
            provider.acquire("user-1", "thread-2")


if __name__ == "__main__":
    unittest.main()
