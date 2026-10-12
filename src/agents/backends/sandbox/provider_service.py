from __future__ import annotations

import asyncio
import hashlib
import json
import re
import weakref
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from threading import Lock

from cubesandbox import Config as CubeConfig
from redis import Redis

from src.configs import config

from .cube_client import CubeClient


def scope_identity(uid: str, thread_id: str) -> dict[str, str]:
    """校验会话路径段，并生成 Cube 中可重新发现的身份。"""
    for label, value in (("uid", uid), ("thread_id", thread_id)):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
            raise ValueError(f"Invalid sandbox {label}")
    return {"app": "agent-stack", "uid": uid, "thread_id": thread_id}


def workspace_paths(uid: str, thread_id: str, skill_root: str | Path | None = None) -> tuple[Path, Path]:
    """让 Composite 与 Host Mount 使用相同目录，并拒绝路径替换。"""
    scope_identity(uid, thread_id)
    root = Path(config.save_dir).resolve()
    workspace = root / "workspaces" / uid / thread_id
    skills = Path(skill_root).absolute() if skill_root else root / "skills"
    if ".." in skills.parts or not skills.is_relative_to(root / "skills"):
        raise ValueError("skill_root must be inside SAVE_DIR/skills")
    for path in (workspace, skills):
        for part in (path, *path.parents):
            if part == root:
                break
            if part.is_symlink() or part.is_junction():
                raise ValueError("Sandbox shared directories must not contain symlinks")
    return workspace, skills


def _mounts(uid: str, thread_id: str, skill_root: str | Path | None) -> str:
    host_root = PurePosixPath(config.cube_host_save_dir)
    if not host_root.is_absolute() or ".." in host_root.parts or "\\" in str(host_root):
        raise ValueError("CUBE_HOST_SAVE_DIR must be an absolute Linux path")
    workspace, skills = workspace_paths(uid, thread_id, skill_root)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "outputs").mkdir(exist_ok=True)
    skills.mkdir(parents=True, exist_ok=True)
    root = Path(config.save_dir).resolve()
    return json.dumps(
        [
            {"hostPath": str(host_root.joinpath(*workspace.relative_to(root).parts)), "mountPath": "/workspace", "readOnly": False},
            {"hostPath": str(host_root.joinpath(*skills.relative_to(root).parts)), "mountPath": "/skill", "readOnly": True},
        ],
        sort_keys=True,
    )


@dataclass
class SandboxState:
    key: tuple[str, str]
    backend: object
    mounts: str
    references: int = 1


class SandboxProviderService:
    """通过 Cube metadata 发现实例；Redis 仅串行化跨进程创建。"""

    def __init__(self, *, client: CubeClient | None = None, redis_client=None):
        sdk_config = CubeConfig(
            api_url=config.cube_api_url,
            api_key=config.cube_api_key or None,
            template_id=config.cube_template_id,
            proxy_node_ip=config.cube_proxy_node_ip,
            proxy_port=config.cube_proxy_port_http,
            sandbox_domain=config.cube_sandbox_domain,
            request_timeout=config.cube_request_timeout_seconds,
        )
        self._client = client or CubeClient(sdk_config, master_url=config.cube_master_url, node_id=config.cube_node_id)
        self._redis = redis_client or Redis.from_url(
            config.redis_url,
            socket_connect_timeout=5,
            socket_timeout=5,
            max_connections=config.redis_pool_max_connections,
        )
        self._lock = Lock()
        self._scope_locks = weakref.WeakValueDictionary()
        self._states: dict[str, SandboxState] = {}
        self._by_scope: dict[tuple[str, str], str] = {}
        self._closed = False

    def _scope_lock(self, key):
        with self._lock:
            if self._closed:
                raise RuntimeError("Sandbox provider is shut down")
            lock = self._scope_locks.get(key)
            if lock is None:
                lock = Lock()
                self._scope_locks[key] = lock
            return lock

    def _creation_lock(self, identity):
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        return self._redis.lock(
            f"sandbox:acquire:{digest}",
            timeout=config.cube_request_timeout_seconds * 4 + 60,
            blocking_timeout=config.cube_request_timeout_seconds,
        )

    def acquire(self, uid: str, thread_id: str, *, skill_root: str | Path | None = None) -> str:
        """重新发现并连接远端，返回一个必须 release 的本地引用。"""
        from .sandbox_backend import CubeSandboxBackend

        identity = scope_identity(uid, thread_id)
        if not self._client.config.template_id:
            raise ValueError("CUBE_TEMPLATE_ID is required before using sandbox tools")
        if config.sandbox_idle_timeout_seconds <= config.sandbox_execute_timeout_seconds + 10:
            raise ValueError("Sandbox idle timeout must exceed the command deadline")
        key = (uid, thread_id)
        mounts = _mounts(uid, thread_id, skill_root)
        mounts_digest = hashlib.sha256(mounts.encode()).hexdigest()
        with self._scope_lock(key), self._creation_lock(identity) as lease:
            match = self._client.find(identity)
            data = None
            if match is not None:
                if match["metadata"].get("mounts_sha256") != mounts_digest:
                    raise RuntimeError("Existing Cube sandbox mounts differ; destroy it explicitly before changing paths")
                data = self._client.connect(match["sandboxID"], config.sandbox_idle_timeout_seconds)
            if data is None:
                if not lease.owned():
                    raise RuntimeError("Sandbox creation lease expired")
                # CubeAPI moves host-mount into annotations and removes it from returned metadata.
                data = self._client.create(
                    {**identity, "host-mount": mounts, "mounts_sha256": mounts_digest},
                    config.sandbox_idle_timeout_seconds,
                )
            if not lease.owned():
                raise RuntimeError("Sandbox creation lease expired; remote result must be rediscovered")
            sandbox_id = data.get("sandboxID")
            if not isinstance(sandbox_id, str) or not sandbox_id:
                raise RuntimeError("Cube returned no sandboxID")
            with self._lock:
                if self._closed:
                    raise RuntimeError("Sandbox provider is shut down")
                state = self._states.get(sandbox_id)
                if state is not None:
                    if state.key != key or state.mounts != mounts:
                        raise RuntimeError("Cube sandbox identity mismatch")
                    state.references += 1
                else:
                    backend = CubeSandboxBackend(
                        uid=uid,
                        thread_id=thread_id,
                        skill_root=skill_root,
                        client=self._client.sandbox(data),
                        provider=self,
                    )
                    self._states[sandbox_id] = SandboxState(key, backend, mounts)
                self._by_scope[key] = sandbox_id
            return sandbox_id

    async def acquire_async(self, uid: str, thread_id: str, **kwargs) -> str:
        task = asyncio.create_task(asyncio.to_thread(self.acquire, uid, thread_id, **kwargs))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            # to_thread 不会随等待者取消；完成后归还它取得的客户端引用。
            def cleanup(done):
                if not done.cancelled() and done.exception() is None:
                    self.release(done.result())

            task.add_done_callback(cleanup)
            raise

    def get(self, sandbox_id: str):
        with self._lock:
            state = self._states.get(sandbox_id)
            return state.backend if state else None

    @contextmanager
    def borrow(self, uid: str, thread_id: str, *, skill_root=None, sandbox_id=None):
        """工具执行期间保留引用，避免另一调用 release 关闭正在使用的 SDK。"""
        mounts = _mounts(uid, thread_id, skill_root)
        with self._lock:
            if self._closed:
                raise RuntimeError("Sandbox provider is shut down")
            sid = sandbox_id or self._by_scope.get((uid, thread_id))
            state = self._states.get(sid)
            if state is not None:
                if state.key != (uid, thread_id) or state.mounts != mounts:
                    raise RuntimeError("Cube sandbox identity mismatch")
                state.references += 1
        if state is None:
            if sandbox_id:
                raise RuntimeError("Sandbox connection was released")
            sid = self.acquire(uid, thread_id, skill_root=skill_root)
        try:
            backend = self.get(sid)
            with backend._operation_lock:
                yield backend._client
        finally:
            self.release(sid)

    def release(self, sandbox_id: str) -> bool:
        client = None
        with self._lock:
            state = self._states.get(sandbox_id)
            if state is None:
                return False
            state.references -= 1
            if state.references == 0:
                self._states.pop(sandbox_id)
                if self._by_scope.get(state.key) == sandbox_id:
                    self._by_scope.pop(state.key)
                client = state.backend._client
        if client is not None:
            client.close()
        return True

    def destroy(self, sandbox_id: str) -> bool:
        info = self._client.info(sandbox_id)
        if info is None:
            return False
        metadata = info.get("metadata", {})
        identity = scope_identity(metadata.get("uid"), metadata.get("thread_id"))
        if metadata.get("app") != identity["app"]:
            raise ValueError("Sandbox belongs to another application")
        with self._scope_lock((identity["uid"], identity["thread_id"])), self._creation_lock(identity):
            self._client.delete(sandbox_id)
        return True

    async def destroy_async(self, sandbox_id: str) -> bool:
        return await asyncio.to_thread(self.destroy, sandbox_id)

    def shutdown(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        # 正在执行的工具保留自己的引用，最后一次 release 才关闭 SDK。
        self._client.close()
        self._redis.close()

    async def shutdown_async(self) -> None:
        await asyncio.to_thread(self.shutdown)


_sandbox_provider_lock = Lock()
_sandbox_provider: SandboxProviderService | None = None


def init_sandbox_provider() -> SandboxProviderService:
    global _sandbox_provider
    with _sandbox_provider_lock:
        if _sandbox_provider is None:
            _sandbox_provider = SandboxProviderService()
        return _sandbox_provider


def get_sandbox_provider() -> SandboxProviderService:
    with _sandbox_provider_lock:
        if _sandbox_provider is None:
            raise RuntimeError("沙箱服务尚未初始化。")
        return _sandbox_provider


async def shutdown_sandbox_provider() -> None:
    global _sandbox_provider
    with _sandbox_provider_lock:
        provider = _sandbox_provider
        _sandbox_provider = None
    if provider is not None:
        await provider.shutdown_async()
