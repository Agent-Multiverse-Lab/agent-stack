from __future__ import annotations

import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from cubesandbox import Config

from src.agents.backends.sandbox import provider_service as service
from src.agents.backends.sandbox.cube_client import CubeClient


class FakeRedis:
    def __init__(self):
        self.locks = {}
        self.guard = threading.Lock()

    def lock(self, key, **kwargs):
        with self.guard:
            lock = self.locks.setdefault(key, threading.Lock())

        class Lease:
            def __enter__(self):
                assert lock.acquire(timeout=3)
                return self

            def __exit__(self, *args):
                lock.release()

            def owned(self):
                return True

        return Lease()

    def close(self):
        pass


class CubeServer:
    """HTTP state survives application client shutdown/restart."""

    def __init__(self):
        self.rows = {}
        self.mounts = {}
        self.creates = 0
        self.error = None
        self.inventory = None
        self.connect_missing = False
        self.created = threading.Event()
        self.resume = None

    def handle(self, request):
        if self.error:
            return httpx.Response(self.error)
        if request.url.path == "/cube/sandbox/inventory":
            assert request.url.params["host_id"] == "agent-stack-node"
            body = (
                self.inventory
                if self.inventory is not None
                else {
                    "ret": {"ret_code": 0},
                    "size": 1,
                    "data": [{"sandbox_id": row["sandboxID"], "labels": row["metadata"]} for row in self.rows.values()],
                }
            )
            return httpx.Response(200, json=body)
        if request.method == "POST" and request.url.path == "/sandboxes":
            data = json.loads(request.content)
            assert data["lifecycle"] == {"onTimeout": "kill"}
            self.creates += 1
            sid = f"cube-{self.creates}"
            # Real CubeAPI stores this in annotations, not in list/get metadata.
            self.mounts[sid] = data["metadata"].pop("host-mount")
            row = {"sandboxID": sid, "metadata": data["metadata"]}
            self.rows[sid] = row
            self.created.set()
            if self.resume:
                assert self.resume.wait(5)
            return httpx.Response(201, json=row)
        sid = request.url.path.split("/")[2]
        if request.url.path.endswith("/connect") and self.connect_missing:
            self.rows.pop(sid, None)
            self.connect_missing = False
        if sid not in self.rows:
            return httpx.Response(404)
        if request.method == "DELETE":
            del self.rows[sid]
            return httpx.Response(204)
        return httpx.Response(200, json=self.rows[sid])


@pytest.fixture
def deployment(tmp_path, monkeypatch):
    monkeypatch.setattr(service.config, "save_dir", str(tmp_path))
    monkeypatch.setattr(service.config, "cube_host_save_dir", "/data/shared/agent-stack")
    server, redis = CubeServer(), FakeRedis()
    providers = []

    def new_provider():
        client = CubeClient(
            Config(template_id="template-test"),
            master_url="http://master",
            node_id="agent-stack-node",
            http_client=httpx.Client(base_url="http://cube", transport=httpx.MockTransport(server.handle)),
        )
        client.sandbox = lambda data: SimpleNamespace(sandbox_id=data["sandboxID"], close=Mock())
        provider = service.SandboxProviderService(client=client, redis_client=redis)
        providers.append(provider)
        return provider

    yield server, new_provider
    for provider in providers:
        for sid, state in list(provider._states.items()):
            for _ in range(state.references):
                provider.release(sid)
        provider.shutdown()


def test_discovery_after_restart_and_user_isolation(deployment):
    server, new = deployment
    first = new()
    sid = first.acquire("alice", "thread")
    sdk = first.get(sid)._client
    first.release(sid)
    sdk.close.assert_called_once()
    first.shutdown()
    second = new()
    assert second.acquire("alice", "thread") == sid
    assert second.acquire("bob", "thread") != sid
    assert server.creates == 2
    mounts = json.loads(server.mounts[sid])
    assert mounts[0]["hostPath"].endswith("/workspaces/alice/thread")
    assert mounts[1]["mountPath"] == "/skill" and mounts[1]["readOnly"]


def test_two_application_providers_create_once(deployment):
    server, new = deployment
    providers = [new(), new()]
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(lambda i: providers[i % 2].acquire("alice", "thread"), range(8)))
    assert len(set(ids)) == 1
    assert server.creates == 1


@pytest.mark.parametrize("status", [401, 403, 500, 503])
def test_management_errors_never_create_another_instance(deployment, status):
    server, new = deployment
    provider = new()
    provider.acquire("alice", "thread")
    server.error = status
    with pytest.raises(httpx.HTTPStatusError):
        provider.acquire("alice", "thread")
    assert server.creates == 1


def test_only_explicit_missing_instance_is_recreated(deployment):
    server, new = deployment
    provider = new()
    first = provider.acquire("alice", "thread")
    provider.release(first)
    server.connect_missing = True
    assert provider.acquire("alice", "thread") != first
    assert server.creates == 2


def test_borrow_keeps_client_alive_after_owner_release(deployment):
    server, new = deployment
    provider = new()
    sid = provider.acquire("alice", "thread")
    with provider.borrow("alice", "thread") as sdk:
        provider.release(sid)
        sdk.close.assert_not_called()
    sdk.close.assert_called_once()
    assert provider.get(sid) is None
    assert sid in server.rows


def test_mount_change_and_duplicate_fail_closed(deployment, monkeypatch):
    server, new = deployment
    provider = new()
    sid = provider.acquire("alice", "thread")
    provider.release(sid)
    row = server.rows[sid]
    server.rows["duplicate"] = {**row, "sandboxID": "duplicate"}
    with pytest.raises(RuntimeError, match="Multiple"):
        provider.acquire("alice", "thread")
    del server.rows["duplicate"]
    monkeypatch.setattr(service.config, "cube_host_save_dir", "/data/shared/changed")
    with pytest.raises(RuntimeError, match="mounts differ"):
        provider.acquire("alice", "thread")
    assert server.creates == 1


@pytest.mark.parametrize(
    "inventory",
    [
        {"ret": {"ret_code": 130404}, "data": []},
        {"ret": {"ret_code": 130500, "ret_msg": "cubelet unreachable"}, "size": 1, "data": []},
        {"ret": {"ret_code": 0}, "size": 1},
        {"ret": {"ret_code": 0}, "size": 0, "data": []},
        {"ret": {"ret_code": 0}, "size": 1, "data": ["invalid"]},
        {},
    ],
    ids=["unknown-node", "unreachable-node", "missing-data", "no-node", "invalid-row", "invalid-body"],
)
def test_failed_or_incomplete_inventory_never_creates(deployment, inventory):
    server, new = deployment
    provider = new()
    provider.acquire("alice", "thread")
    server.inventory = inventory
    with pytest.raises(RuntimeError, match="inventory"):
        provider.acquire("alice", "thread")
    assert server.creates == 1


def test_unrelated_null_metadata_does_not_block_discovery(deployment):
    server, new = deployment
    server.rows["other"] = {"sandboxID": "other", "metadata": None}
    assert new().acquire("alice", "thread") == "cube-1"


@pytest.mark.parametrize("uid,thread", [("..", "thread"), ("alice", "../other"), ("a/b", "thread")])
def test_invalid_workspace_identity_rejected(deployment, uid, thread):
    server, new = deployment
    with pytest.raises(ValueError):
        new().acquire(uid, thread)
    assert server.creates == 0


def test_canceled_acquire_eventually_releases_client(deployment):
    server, new = deployment
    server.resume = threading.Event()
    provider = new()

    async def run():
        task = asyncio.create_task(provider.acquire_async("alice", "thread"))
        assert await asyncio.to_thread(server.created.wait, 3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        server.resume.set()
        await asyncio.sleep(0.2)
        assert provider.get("cube-1") is None

    asyncio.run(run())
    assert server.creates == 1


def test_shutdown_preserves_remote_and_rejects_new_use(deployment):
    server, new = deployment
    provider = new()
    sid = provider.acquire("alice", "thread")
    provider.shutdown()
    provider.shutdown()
    with pytest.raises(RuntimeError, match="shut down"):
        provider.acquire("alice", "thread")
    provider.release(sid)
    assert sid in server.rows


def test_explicit_destroy_preserves_host_files(deployment, tmp_path):
    server, new = deployment
    provider = new()
    sid = provider.acquire("alice", "thread")
    provider.release(sid)
    artifact = tmp_path / "workspaces/alice/thread/outputs/result.txt"
    artifact.write_text("retained")
    assert provider.destroy(sid)
    assert not server.rows
    assert artifact.read_text() == "retained"
