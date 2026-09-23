"""Authenticated access to a conversation's real sandbox workspace."""

from __future__ import annotations

import asyncio
import posixpath
from pathlib import PurePosixPath

from sqlalchemy.ext.asyncio import AsyncSession

from server.entities.sandbox import (
    SandboxFileContentResponse,
    SandboxWorkspaceEntry,
    SandboxWorkspaceResponse,
)
from src.agents.backends.sandbox import get_sandbox_provider
from src.database.repositories import ConversationRepository

WORKSPACE_PATH = "/workspace"
SANDBOX_WORKSPACE_PATH = "/home/gem/user-data/workspace"
MAX_FILE_PREVIEW_LINES = 2000
MAX_FILE_PREVIEW_CHARS = 200_000

_CODE_EXTENSIONS = {
    ".c", ".cpp", ".css", ".go", ".html", ".java", ".js", ".jsx",
    ".py", ".rs", ".sh", ".sql", ".ts", ".tsx", ".vue",
}
_DATA_EXTENSIONS = {
    ".csv", ".json", ".jsonl", ".parquet", ".toml", ".xml", ".yaml", ".yml",
}
_IMAGE_EXTENSIONS = {
    ".avif", ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp",
}


def normalize_workspace_path(path: str) -> str:
    normalized = posixpath.normpath("/" + str(path or "").lstrip("/"))
    if normalized != WORKSPACE_PATH and not normalized.startswith(f"{WORKSPACE_PATH}/"):
        raise ValueError("path must be inside /workspace")
    return normalized


def to_sandbox_path(path: str) -> str:
    normalized = normalize_workspace_path(path)
    suffix = normalized.removeprefix(WORKSPACE_PATH).lstrip("/")
    return posixpath.join(SANDBOX_WORKSPACE_PATH, suffix)


def to_workspace_path(path: str) -> str:
    normalized = posixpath.normpath(path)
    if normalized != SANDBOX_WORKSPACE_PATH and not normalized.startswith(
        f"{SANDBOX_WORKSPACE_PATH}/"
    ):
        raise ValueError("sandbox returned a path outside the workspace")
    suffix = normalized.removeprefix(SANDBOX_WORKSPACE_PATH).lstrip("/")
    return posixpath.join(WORKSPACE_PATH, suffix)


def _file_type(path: str) -> str | None:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix in _CODE_EXTENSIONS:
        return "code"
    if suffix in _DATA_EXTENSIONS:
        return "data"
    if suffix in _IMAGE_EXTENSIONS:
        return "image"
    return "document" if suffix else None


async def _get_owned_sandbox(
    db: AsyncSession,
    *,
    uid: str,
    thread_id: str,
):
    normalized_thread_id = str(thread_id).strip()
    conversation = await ConversationRepository(
        db
    ).get_conversation_by_thread_id_for_user(normalized_thread_id, uid)
    if conversation is None:
        raise LookupError("Conversation not found")

    provider = get_sandbox_provider()
    sandbox_id = await provider.acquire_async(
        uid,
        normalized_thread_id,
        file_thread_id=normalized_thread_id,
        skills_thread_id=normalized_thread_id,
    )
    sandbox = provider.get(sandbox_id)
    if sandbox is None:
        raise RuntimeError("Sandbox execution backend is unavailable")
    return normalized_thread_id, sandbox_id, sandbox


async def list_workspace(
    db: AsyncSession,
    *,
    uid: str,
    thread_id: str,
    path: str,
) -> SandboxWorkspaceResponse:
    workspace_path = normalize_workspace_path(path)
    normalized_thread_id, sandbox_id, sandbox = await _get_owned_sandbox(
        db,
        uid=uid,
        thread_id=thread_id,
    )

    result = await asyncio.to_thread(sandbox.ls, to_sandbox_path(workspace_path))
    error = getattr(result, "error", None)
    if error:
        raise RuntimeError(str(error))

    entries = []
    for item in getattr(result, "entries", []) or []:
        item_path = to_workspace_path(str(item["path"]))
        is_directory = bool(item.get("is_dir"))
        entries.append(
            SandboxWorkspaceEntry(
                name=posixpath.basename(item_path.rstrip("/")),
                path=item_path,
                kind="directory" if is_directory else "file",
                size=item.get("size") if isinstance(item.get("size"), int) else None,
                modified_at=str(item.get("modified_at") or ""),
                file_type=None if is_directory else _file_type(item_path),
            )
        )

    entries.sort(key=lambda entry: (entry.kind != "directory", entry.name.lower()))
    return SandboxWorkspaceResponse(
        thread_id=normalized_thread_id,
        sandbox_id=sandbox_id,
        path=workspace_path,
        entries=entries,
    )


async def read_workspace_file(
    db: AsyncSession,
    *,
    uid: str,
    thread_id: str,
    path: str,
) -> SandboxFileContentResponse:
    workspace_path = normalize_workspace_path(path)
    if workspace_path == WORKSPACE_PATH:
        raise ValueError("path must point to a file inside /workspace")

    normalized_thread_id, sandbox_id, sandbox = await _get_owned_sandbox(
        db,
        uid=uid,
        thread_id=thread_id,
    )
    result = await asyncio.to_thread(
        sandbox.read,
        to_sandbox_path(workspace_path),
        0,
        MAX_FILE_PREVIEW_LINES + 1,
    )
    error = getattr(result, "error", None)
    if error:
        raise RuntimeError(str(error))

    file_data = getattr(result, "file_data", None) or {}
    content = str(file_data.get("content") or "")
    encoding = str(file_data.get("encoding") or "utf-8")
    if encoding.lower().replace("_", "-") not in {"utf-8", "utf8"}:
        raise ValueError("file is not UTF-8 text")

    lines = content.splitlines(keepends=True)
    truncated = len(lines) > MAX_FILE_PREVIEW_LINES
    if truncated:
        content = "".join(lines[:MAX_FILE_PREVIEW_LINES])
    if len(content) > MAX_FILE_PREVIEW_CHARS:
        content = content[:MAX_FILE_PREVIEW_CHARS]
        truncated = True

    return SandboxFileContentResponse(
        thread_id=normalized_thread_id,
        sandbox_id=sandbox_id,
        path=workspace_path,
        content=content,
        encoding=encoding,
        truncated=truncated,
    )
