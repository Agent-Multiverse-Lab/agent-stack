"""Authenticated access to a conversation's real sandbox workspace."""

from __future__ import annotations

import asyncio
import json
import posixpath
import shlex
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Literal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from server.entities.sandbox import (
    SandboxFileContentResponse,
    SandboxWorkspaceEntry,
    SandboxWorkspaceResponse,
)
from src.agents.backends.sandbox import get_sandbox_provider
from src.database.repositories import ConversationRepository

WORKSPACE_PATH = "/workspace"
MAX_ARTIFACT_DOWNLOAD_BYTES = 128 * 1024 * 1024
MAX_FILE_PREVIEW_LINES = 2000
MAX_FILE_PREVIEW_CHARS = 200_000

# Run inside the owned VM; keep file operations within its workspace.
_FILE_OPERATION_SCRIPT = r'''
import json, os, stat, sys, tempfile
from pathlib import Path

def apply_operation(root, request):
    root = root.resolve()
    path = root / request['path'].removeprefix('/workspace/')
    for part in [path, *path.parents]:
        if part == root:
            break
        if part.is_symlink():
            raise ValueError('Symbolic links cannot be modified')
    path.resolve().relative_to(root)
    if not path.is_file():
        if path.exists():
            raise ValueError('Choose a regular file')
        raise FileNotFoundError('File not found')
    operation = request['operation']
    if operation == 'rename':
        target = path.with_name(request['name'])
        # Exclusive creation keeps an existing destination intact.
        try:
            os.link(path, target)
        except FileExistsError:
            raise FileExistsError('A file with this name already exists')
        path.unlink()
        return {'path': '/workspace/' + target.relative_to(root).as_posix()}
    if operation == 'delete':
        path.unlink()
        return {'path': request['path']}
    if operation in {'read', 'write'}:
        with path.open('r', encoding='utf-8', newline='') as source:
            original = source.read(200_001)
        if '\x00' in original:
            raise ValueError('Only complete UTF-8 text files can be edited')
        if operation == 'read':
            return {'path': request['path'], 'content': original[:200_000], 'encoding': 'utf-8',
                    'truncated': len(original) > 200_000 or len(original.splitlines()) > 2000}
        if len(original) > 200_000 or '\x00' in request['content']:
            raise ValueError('Only complete UTF-8 text files can be edited')
        if original != request['previous_content']:
            raise FileExistsError('File changed. Reopen it before saving')
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='', dir=path.parent, delete=False) as target:
                temporary = Path(target.name)
                content = request['content']
                if '\r\n' in original and '\n' not in original.replace('\r\n', ''):
                    content = content.replace('\r\n', '\n').replace('\n', '\r\n')
                target.write(content)
            os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return {'path': request['path']}
    raise ValueError('Unknown file operation')

if __name__ == '__main__':
    argument = sys.argv[1]
    staged = argument.startswith('/tmp/agent-stack-file-')
    try:
        request = json.loads(Path(argument).read_text(encoding='utf-8') if staged else argument)
        print(json.dumps(apply_operation(Path('/workspace'), request)))
    except FileExistsError as error:
        print(json.dumps({'kind': 'conflict', 'error': str(error)}))
    except FileNotFoundError:
        print(json.dumps({'kind': 'not_found', 'error': 'File not found'}))
    except (ValueError, UnicodeError) as error:
        print(json.dumps({'kind': 'invalid', 'error': str(error)}))
    except OSError as error:
        print(json.dumps({'kind': 'failure', 'error': str(error)}))
    finally:
        if staged:
            Path(argument).unlink(missing_ok=True)
'''

_CODE_EXTENSIONS = {
    ".c",
    ".cpp",
    ".css",
    ".go",
    ".html",
    ".java",
    ".js",
    ".jsx",
    ".py",
    ".rs",
    ".sh",
    ".sql",
    ".ts",
    ".tsx",
    ".vue",
}
_DATA_EXTENSIONS = {
    ".csv",
    ".json",
    ".jsonl",
    ".parquet",
    ".toml",
    ".xml",
    ".yaml",
    ".yml",
}
_IMAGE_EXTENSIONS = {
    ".avif",
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".webp",
}


def normalize_workspace_path(path: str) -> str:
    normalized = posixpath.normpath("/" + str(path or "").lstrip("/"))
    if normalized != WORKSPACE_PATH and not normalized.startswith(f"{WORKSPACE_PATH}/"):
        raise ValueError("path must be inside /workspace")
    return normalized


def to_sandbox_path(path: str) -> str:
    return normalize_workspace_path(path)


def to_workspace_path(path: str) -> str:
    normalized = posixpath.normpath(path)
    if normalized != WORKSPACE_PATH and not normalized.startswith(f"{WORKSPACE_PATH}/"):
        raise ValueError("sandbox returned a path outside the workspace")
    suffix = normalized.removeprefix(WORKSPACE_PATH).lstrip("/")
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
    conversation = await ConversationRepository(db).get_conversation_by_thread_id_for_user(normalized_thread_id, uid)
    if conversation is None:
        raise LookupError("Conversation not found")

    provider = get_sandbox_provider()
    sandbox_id = await provider.acquire_async(
        uid,
        normalized_thread_id,
    )
    sandbox = provider.get(sandbox_id)
    if sandbox is None:
        provider.release(sandbox_id)
        raise RuntimeError("Sandbox execution backend is unavailable")
    return normalized_thread_id, sandbox_id, sandbox, provider


async def list_workspace(
    db: AsyncSession,
    *,
    uid: str,
    thread_id: str,
    path: str,
) -> SandboxWorkspaceResponse:
    workspace_path = normalize_workspace_path(path)
    normalized_thread_id, sandbox_id, sandbox, provider = await _get_owned_sandbox(
        db,
        uid=uid,
        thread_id=thread_id,
    )

    try:
        result = await asyncio.to_thread(sandbox.ls, to_sandbox_path(workspace_path))
    finally:
        provider.release(sandbox_id)
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
                modified_at=datetime.fromtimestamp(item["mtime"], UTC).isoformat() if isinstance(item.get("mtime"), (int, float)) else "",
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
    editable: bool = False,
) -> SandboxFileContentResponse:
    workspace_path = normalize_workspace_path(path)
    if workspace_path == WORKSPACE_PATH:
        raise ValueError("path must point to a file inside /workspace")

    normalized_thread_id, sandbox_id, sandbox, provider = await _get_owned_sandbox(
        db,
        uid=uid,
        thread_id=thread_id,
    )
    try:
        if editable:
            response = await asyncio.to_thread(
                _execute_file_operation, sandbox, {"operation": "read", "path": workspace_path},
            )
            return SandboxFileContentResponse(
                thread_id=normalized_thread_id, sandbox_id=sandbox_id, **response,
            )
        result = await asyncio.to_thread(
            sandbox.read,
            to_sandbox_path(workspace_path),
            0,
            MAX_FILE_PREVIEW_LINES + 1,
        )
    finally:
        provider.release(sandbox_id)
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


_WORKSPACE_FILE_CHECK_SCRIPT = r'''
import json, sys
from pathlib import Path

root = Path("/workspace").resolve()
path = root / sys.argv[1].removeprefix("/workspace/")
try:
    for part in [path, *path.parents]:
        if part == root:
            break
        if part.is_symlink():
            raise ValueError("symbolic links are not allowed")
    resolved = path.resolve()
    resolved.relative_to(root)
    if not resolved.is_file():
        raise ValueError("Choose a regular file")
    print(json.dumps({"ok": True, "size": resolved.stat().st_size}))
except Exception as error:
    print(json.dumps({"ok": False, "error": str(error)}))
'''


async def download_workspace_file(
    db: AsyncSession,
    *,
    uid: str,
    thread_id: str,
    path: str,
) -> tuple[bytes, str]:
    """读取当前会话工作区内普通文件字节，供交付物下载与图片预览。"""
    workspace_path = normalize_workspace_path(path)
    if workspace_path == WORKSPACE_PATH:
        raise ValueError("path must point to a file inside /workspace")
    _, sandbox_id, sandbox, provider = await _get_owned_sandbox(
        db, uid=uid, thread_id=thread_id,
    )
    try:
        check = await asyncio.to_thread(
            sandbox.execute,
            f"python3 -c {shlex.quote(_WORKSPACE_FILE_CHECK_SCRIPT)} {shlex.quote(workspace_path)}",
        )
        try:
            checked = json.loads(check.output)
        except (ValueError, TypeError) as exc:
            raise RuntimeError("Invalid workspace file check response") from exc
        if check.exit_code or not checked.get("ok"):
            error = str(checked.get("error") or "File not found")
            if "not exist" in error.lower() or "not found" in error.lower() or "no such" in error.lower():
                raise FileNotFoundError(error)
            raise ValueError(error)
        if int(checked.get("size") or 0) > MAX_ARTIFACT_DOWNLOAD_BYTES:
            raise ValueError("file is too large to download")
        responses = await asyncio.to_thread(
            sandbox.download_files, [to_sandbox_path(workspace_path)],
        )
    finally:
        provider.release(sandbox_id)
    if not responses:
        raise RuntimeError("File download failed")
    response = responses[0]
    error = getattr(response, "error", None)
    if error:
        if str(error) == "file_not_found":
            raise FileNotFoundError("File not found")
        if str(error) == "is_directory":
            raise ValueError("Choose a regular file")
        if str(error) == "permission_denied":
            raise PermissionError("File access denied")
        raise RuntimeError(str(error))
    content = getattr(response, "content", None)
    if content is None:
        raise FileNotFoundError("File not found")
    if isinstance(content, str):
        content = content.encode("utf-8")
    if len(content) > MAX_ARTIFACT_DOWNLOAD_BYTES:
        raise ValueError("file is too large to download")
    return content, posixpath.basename(workspace_path)


async def mutate_workspace_file(
    db: AsyncSession,
    *,
    uid: str,
    thread_id: str,
    path: str,
    operation: Literal["rename", "write", "delete"],
    name: str | None = None,
    content: str | None = None,
    previous_content: str | None = None,
) -> str:
    workspace_path = normalize_workspace_path(path)
    if workspace_path == WORKSPACE_PATH or "\x00" in workspace_path:
        raise ValueError("Choose a file inside /workspace")
    if operation == "rename" and (
        not name or name in {".", ".."} or any(char in name for char in "/\\\x00")
    ):
        raise ValueError("Enter a file name without path separators")
    if operation == "write" and (
        content is None or previous_content is None
        or len(content) > MAX_FILE_PREVIEW_CHARS
        or len(previous_content) > MAX_FILE_PREVIEW_CHARS
    ):
        raise ValueError("Only complete UTF-8 text files can be edited")
    _, sandbox_id, sandbox, provider = await _get_owned_sandbox(
        db, uid=uid, thread_id=thread_id,
    )
    request = {"operation": operation, "path": workspace_path}
    if operation == "rename":
        request["name"] = name
    elif operation == "write":
        request.update(content=content, previous_content=previous_content)

    try:
        response = await asyncio.to_thread(_execute_file_operation, sandbox, request)
        return to_workspace_path(response["path"])
    finally:
        provider.release(sandbox_id)


def _execute_file_operation(sandbox, request: dict) -> dict:
    argument = json.dumps(request, ensure_ascii=False)
    if request["operation"] == "write":
        # Upload the editor payload rather than exceeding shell argument limits.
        staged_path = f"/tmp/agent-stack-file-{uuid4().hex}.json"
        uploaded = sandbox.upload_files([(staged_path, argument.encode("utf-8"))])
        if not uploaded or uploaded[0].error:
            raise RuntimeError(str(uploaded[0].error if uploaded else "File upload failed"))
        argument = staged_path
    result = sandbox.execute(f"python3 -c {shlex.quote(_FILE_OPERATION_SCRIPT)} {shlex.quote(argument)}")
    if result.exit_code:
        raise RuntimeError(result.output or "File operation failed")
    try:
        response = json.loads(result.output)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Invalid file operation response") from exc
    if response.get("error"):
        error_type = {"conflict": FileExistsError, "not_found": FileNotFoundError, "invalid": ValueError}.get(response.get("kind"), RuntimeError)
        raise error_type(response["error"])
    return response

