"""长期记忆 backends（本地 FilesystemBackend）。

两种 scope：
- user-scoped：uid
- agent-scoped：uid + agent_slug（该用户对该 agent 的长期记忆，跨 thread）

存储默认落盘，不走 PostgresStore。不含 thread_id（本轮草稿走 workspace/State）。

Composite 路由示例::

    routes={
        "/memory/": UserMemoriesBackend.from_context(context),
        "/agent_memory/": AgentMemoriesBackend.from_context(
            context, agent_slug="leader"
        ),
    }

路径映射::

    /memory/preferences.md
        → {save_dir}/memories/users/{uid}/preferences.md
    /agent_memory/AGENTS.md
        → {save_dir}/memories/users/{uid}/agents/{agent_slug}/AGENTS.md
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from deepagents.backends.filesystem import FilesystemBackend

from src.agents.base_context import BaseContext
from src.configs.config import config as sys_config

# Composite 虚拟前缀
MEMORY_ROUTE_PREFIX = "/memory/"
AGENT_MEMORY_ROUTE_PREFIX = "/agent_memory/"


def _safe_id(value: str | None, *, default: str) -> str:
    text = (value or "").strip()
    return text or default


def _memories_base(base: str | Path | None = None) -> Path:
    return Path(base) if base is not None else Path(sys_config.save_dir) / "memories"


def memory_root_for_uid(uid: str, *, base: str | Path | None = None) -> Path:
    """user-scoped：{base}/users/{uid}。"""
    return (_memories_base(base) / "users" / _safe_id(uid, default="anonymous")).resolve()


def memory_root_for_user_agent(
    uid: str,
    agent_slug: str,
    *,
    base: str | Path | None = None,
) -> Path:
    """agent-scoped（uid + agent_slug）：{base}/users/{uid}/agents/{agent_slug}。"""
    return (
        _memories_base(base)
        / "users"
        / _safe_id(uid, default="anonymous")
        / "agents"
        / _safe_id(agent_slug, default="default")
    ).resolve()


class _MemoriesFilesystemBackend(FilesystemBackend):
    """记忆 backend 公共初始化。"""

    scope: str
    memory_root: Path

    def __init__(
        self,
        *,
        scope: str,
        root_dir: Path,
        ensure_dir: bool,
        max_file_size_mb: int,
    ) -> None:
        self.scope = scope
        resolved = root_dir.resolve()
        if ensure_dir:
            resolved.mkdir(parents=True, exist_ok=True)
        super().__init__(
            root_dir=str(resolved),
            virtual_mode=True,
            max_file_size_mb=max_file_size_mb,
        )
        self.memory_root = resolved

    def __repr__(self) -> str:
        return f"{type(self).__name__}(scope={self.scope!r}, root={str(self.memory_root)!r})"


class UserMemoriesBackend(_MemoriesFilesystemBackend):
    """User-scoped 记忆：仅 uid，跨 thread。"""

    def __init__(
        self,
        uid: str,
        *,
        root_dir: str | Path | None = None,
        ensure_dir: bool = True,
        max_file_size_mb: int = 10,
    ) -> None:
        self.uid = _safe_id(uid, default="anonymous")
        resolved = (
            Path(root_dir).resolve()
            if root_dir is not None
            else memory_root_for_uid(self.uid)
        )
        super().__init__(
            scope="user",
            root_dir=resolved,
            ensure_dir=ensure_dir,
            max_file_size_mb=max_file_size_mb,
        )

    @classmethod
    def from_context(
        cls,
        context: BaseContext | Any,
        *,
        root_dir: str | Path | None = None,
        **kwargs: Any,
    ) -> UserMemoriesBackend:
        uid = getattr(context, "uid", None) or "anonymous"
        return cls(uid=str(uid), root_dir=root_dir, **kwargs)

    def __repr__(self) -> str:
        return f"UserMemoriesBackend(uid={self.uid!r}, root={str(self.memory_root)!r})"


class AgentMemoriesBackend(_MemoriesFilesystemBackend):
    """Agent 记忆：uid + agent_slug，跨 thread。

    同一用户、同一 agent 的长期偏好/产物；不同用户互不可见。
    不含 thread_id（本轮草稿请用 workspace / StateBackend）。
    """

    def __init__(
        self,
        uid: str,
        agent_slug: str,
        *,
        root_dir: str | Path | None = None,
        ensure_dir: bool = True,
        max_file_size_mb: int = 10,
    ) -> None:
        self.uid = _safe_id(uid, default="anonymous")
        self.agent_slug = _safe_id(agent_slug, default="default")
        resolved = (
            Path(root_dir).resolve()
            if root_dir is not None
            else memory_root_for_user_agent(self.uid, self.agent_slug)
        )
        super().__init__(
            scope="user_agent",
            root_dir=resolved,
            ensure_dir=ensure_dir,
            max_file_size_mb=max_file_size_mb,
        )

    @classmethod
    def from_context(
        cls,
        context: BaseContext | Any,
        *,
        agent_slug: str | None = None,
        root_dir: str | Path | None = None,
        **kwargs: Any,
    ) -> AgentMemoriesBackend:
        """uid 来自 context；agent_slug 优先显式参数。

        agent_slug 回退：context.agent_slug / context.agent_id / context 类型名。
        """
        uid = getattr(context, "uid", None) or "anonymous"
        resolved_slug = (
            agent_slug
            or getattr(context, "agent_slug", None)
            or getattr(context, "agent_id", None)
            or type(context).__name__.removesuffix("Context").lower()
            or "default"
        )
        return cls(
            uid=str(uid),
            agent_slug=str(resolved_slug),
            root_dir=root_dir,
            **kwargs,
        )

    def __repr__(self) -> str:
        return (
            f"AgentMemoriesBackend(uid={self.uid!r}, "
            f"agent_slug={self.agent_slug!r}, root={str(self.memory_root)!r})"
        )
