from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import TYPE_CHECKING

from src.configs import config

from .provision_client import SandboxProvision, SandboxProvisionClient

if TYPE_CHECKING:
    from .sandbox_backend import CustomSandbox

SandboxCacheKey = tuple[str, str]


def _required(value: str, label: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{label} is required.")
    return normalized


def _build_cache_key(uid: str, thread_id: str) -> SandboxCacheKey:
    return _required(uid, "uid"), _required(thread_id, "thread_id")


def _build_sandbox_id(key: SandboxCacheKey) -> str:
    digest = hashlib.sha256("\0".join(key).encode("utf-8")).hexdigest()[:16]
    return f"s2c-{digest}"


def _create_custom_sandbox(**kwargs: object) -> CustomSandbox:
    from .sandbox_backend import CustomSandbox

    return CustomSandbox(**kwargs)


@dataclass(slots=True)
class SandboxState:
    """会话与活动沙箱在当前进程内的绑定状态。"""

    cache_key: SandboxCacheKey
    provision: SandboxProvision
    sandbox: CustomSandbox
    acquired_at: datetime
    last_accessed_at: datetime

    @property
    def sandbox_id(self) -> str:
        return self.provision.sandbox_id


class SandboxProviderService:
    """基于供应客户端管理当前进程内的沙箱绑定。"""

    def __init__(self) -> None:
        self._client = SandboxProvisionClient(config.sandbox_provisioner_url)
        self._sandbox_factory = _create_custom_sandbox

        # 状态锁只保护本地字典；持有这把全局锁时不得请求供应服务。
        self._state_lock = Lock()
        self._acquire_locks: dict[SandboxCacheKey, Lock] = {}
        self._buckets: dict[SandboxCacheKey, SandboxState] = {}
        self._states_by_id: dict[str, SandboxState] = {}
        self._closed = False

    def acquire(
        self,
        uid: str,
        thread_id: str,
        *,
        file_thread_id: str | None = None,
        skills_thread_id: str | None = None,
        env: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        execute_timeout: int | None = None,
    ) -> str:
        """获取同一用户和会话可复用的沙箱 ID。"""
        key = _build_cache_key(uid, thread_id)
        acquire_lock = self._get_acquire_lock(key)

        # 只串行化当前用户和会话；其他会话仍可并行创建，并保证同一键的请求幂等。
        with acquire_lock:
            self._ensure_open()
            with self._state_lock:
                current = self._buckets.get(key)

            sandbox_id = current.sandbox_id if current else _build_sandbox_id(key)
            provision = self._client.get(sandbox_id)
            if provision is None:
                provision = self._client.create(
                    sandbox_id=sandbox_id,
                    thread_id=key[1],
                    user_id=key[0],
                    file_thread_id=file_thread_id,
                    skills_thread_id=skills_thread_id,
                    env=env,
                )

            if (
                current is not None
                and current.provision.sandbox_url == provision.sandbox_url
            ):
                sandbox = current.sandbox
                acquired_at = current.acquired_at
            else:
                sandbox_kwargs: dict[str, object] = {
                    "sandbox_id": provision.sandbox_id,
                }
                if headers is not None:
                    sandbox_kwargs["headers"] = dict(headers)
                if execute_timeout is not None:
                    sandbox_kwargs["execute_timeout"] = execute_timeout
                sandbox = self._sandbox_factory(
                    thread_id=key[1],
                    uid=key[0],
                    sandbox_url=provision.sandbox_url,
                    **sandbox_kwargs,
                )
                acquired_at = datetime.now(UTC)

            now = datetime.now(UTC)
            state = SandboxState(
                cache_key=key,
                provision=provision,
                sandbox=sandbox,
                acquired_at=acquired_at,
                last_accessed_at=now,
            )
            with self._state_lock:
                if self._closed:
                    raise RuntimeError("Sandbox provider service is shut down.")
                self._buckets[key] = state
                self._states_by_id[provision.sandbox_id] = state
            return provision.sandbox_id

    async def acquire_async(
        self,
        uid: str,
        thread_id: str,
        **kwargs: object,
    ) -> str:
        """在线程中执行同步供应请求，避免阻塞事件循环。"""
        return await asyncio.to_thread(self.acquire, uid, thread_id, **kwargs)

    def get(self, sandbox_id: str) -> CustomSandbox | None:
        """从本地缓存返回已经获取的沙箱执行后端。"""
        normalized_id = _required(sandbox_id, "sandbox_id")
        with self._state_lock:
            state = self._states_by_id.get(normalized_id)
            if state is None:
                return None
            state.last_accessed_at = datetime.now(UTC)
            return state.sandbox

    def release(self, sandbox_id: str) -> bool:
        """释放本地绑定，但不删除远端沙箱。"""
        normalized_id = _required(sandbox_id, "sandbox_id")
        with self._state_lock:
            state = self._states_by_id.get(normalized_id)
            acquire_lock = (
                self._acquire_locks.get(state.cache_key) if state is not None else None
            )
        if acquire_lock is None:
            return False
        with acquire_lock:
            with self._state_lock:
                return self._remove_state_unlocked(normalized_id) is not None

    def destroy(self, sandbox_id: str) -> bool:
        """删除远端沙箱并移除其本地绑定。"""
        normalized_id = _required(sandbox_id, "sandbox_id")
        with self._state_lock:
            state = self._states_by_id.get(normalized_id)
            acquire_lock = (
                self._acquire_locks.get(state.cache_key) if state is not None else None
            )

        if acquire_lock is None:
            deleted = self._client.delete(normalized_id)
            with self._state_lock:
                self._remove_state_unlocked(normalized_id)
            return deleted

        with acquire_lock:
            self._ensure_open()
            deleted = self._client.delete(normalized_id)
            with self._state_lock:
                self._remove_state_unlocked(normalized_id)
            return deleted

    async def destroy_async(self, sandbox_id: str) -> bool:
        return await asyncio.to_thread(self.destroy, sandbox_id)

    def shutdown(self) -> None:
        """停止当前服务并关闭进程内资源。

        这里不会删除远端沙箱；物理清理由供应服务的空闲回收器或显式
        ``destroy`` 调用负责。
        """
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
            self._buckets.clear()
            self._states_by_id.clear()
            self._acquire_locks.clear()
        self._client.close()

    async def shutdown_async(self) -> None:
        await asyncio.to_thread(self.shutdown)

    def _get_acquire_lock(self, key: SandboxCacheKey) -> Lock:
        with self._state_lock:
            if self._closed:
                raise RuntimeError("Sandbox provider service is shut down.")
            lock = self._acquire_locks.get(key)
            if lock is None:
                lock = Lock()
                self._acquire_locks[key] = lock
            return lock

    def _ensure_open(self) -> None:
        with self._state_lock:
            if self._closed:
                raise RuntimeError("Sandbox provider service is shut down.")

    def _remove_state_unlocked(self, sandbox_id: str) -> SandboxState | None:
        state = self._states_by_id.pop(sandbox_id, None)
        if state is not None and self._buckets.get(state.cache_key) is state:
            self._buckets.pop(state.cache_key, None)
        return state


_sandbox_provider_lock = Lock()
_sandbox_provider: SandboxProviderService | None = None


def init_sandbox_provider() -> SandboxProviderService:
    """初始化并返回当前进程唯一的沙箱服务实例。"""
    global _sandbox_provider

    with _sandbox_provider_lock:
        if _sandbox_provider is None:
            _sandbox_provider = SandboxProviderService()
        return _sandbox_provider


def get_sandbox_provider() -> SandboxProviderService:
    """获取已经初始化的沙箱服务实例。"""
    with _sandbox_provider_lock:
        if _sandbox_provider is None:
            raise RuntimeError("沙箱服务尚未初始化。")
        return _sandbox_provider


async def shutdown_sandbox_provider() -> None:
    """关闭并清除当前进程的沙箱服务实例。"""
    global _sandbox_provider

    with _sandbox_provider_lock:
        provider = _sandbox_provider
        _sandbox_provider = None

    if provider is not None:
        await provider.shutdown_async()
