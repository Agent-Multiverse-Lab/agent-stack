from __future__ import annotations

import base64
import json
import shlex
from contextlib import nullcontext
from pathlib import PurePosixPath
from threading import RLock

from deepagents.backends.protocol import ExecuteResponse, FileDownloadResponse, FileUploadResponse
from deepagents.backends.sandbox import BaseSandbox

from src.configs import config

_CHUNK_SIZE = 64 * 1024
_DOWNLOAD_SCRIPT = """
import base64, json, os, sys
path, offset, expected = json.loads(base64.b64decode(sys.argv[1]))
try:
    with open(path, 'rb') as f:
        st = os.fstat(f.fileno())
        signature = [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns]
        if expected is not None and signature != expected:
            raise RuntimeError('file changed during download')
        f.seek(offset)
        chunk = f.read(65536)
        after = os.fstat(f.fileno())
        if signature != [after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns]:
            raise RuntimeError('file changed during download')
        print(json.dumps({'signature': signature, 'data': base64.b64encode(chunk).decode()}))
except FileNotFoundError:
    print(json.dumps({'error': 'file_not_found'}))
except IsADirectoryError:
    print(json.dumps({'error': 'is_directory'}))
except PermissionError:
    print(json.dumps({'error': 'permission_denied'}))
except Exception as e:
    print(json.dumps({'error': str(e)}))
"""


class CubeSandboxBackend(BaseSandbox):
    """保留 DeepAgents 文件协议，仅适配 Cube 命令和字节传输。"""

    def __init__(self, *, uid: str, thread_id: str, skill_root=None, client=None, provider=None):
        self._uid = uid
        self._thread_id = thread_id
        self._skill_root = skill_root
        self._client = client
        self._provider = provider
        self._operation_lock = RLock()

    def _connection(self):
        from .provider_service import get_sandbox_provider

        if self._client is not None and self._provider is None:
            return nullcontext(self._client)
        provider = self._provider or get_sandbox_provider()
        return provider.borrow(
            self._uid,
            self._thread_id,
            skill_root=self._skill_root,
            sandbox_id=self._client.sandbox_id if self._client is not None else None,
        )

    @property
    def id(self) -> str:
        if self._client is not None:
            return self._client.sandbox_id
        with self._connection() as client:
            return client.sandbox_id

    @staticmethod
    def _run(client, command: str, timeout: int | None = None):
        seconds = config.sandbox_execute_timeout_seconds if timeout is None else min(timeout, config.sandbox_execute_timeout_seconds)
        if seconds <= 0:
            raise ValueError("Command timeout must be positive")
        # SDK 读超时不负责终止子进程，使用 VM 内的进程组超时作为硬上限。
        wrapped = f"timeout --signal=TERM --kill-after=5s {int(seconds)}s bash -lc {shlex.quote(command)}"
        return client.commands.run(wrapped, cwd="/workspace", timeout=seconds + 10)

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        if not isinstance(command, str) or not command.strip():
            return ExecuteResponse(output="Error: command must not be empty", exit_code=1)
        try:
            with self._connection() as client, self._operation_lock:
                result = self._run(client, command, timeout)
            output = result.stdout
            if result.stderr:
                output += ("\n" if output and not output.endswith("\n") else "") + result.stderr
            # BaseSandbox 使用完整 JSON 解析文件结果，不能在这里截断。
            return ExecuteResponse(output=output, exit_code=result.exit_code, truncated=False)
        except Exception as exc:
            return ExecuteResponse(output=f"Error executing command ({type(exc).__name__}): {exc}", exit_code=1)

    @staticmethod
    def _valid_path(path: str) -> bool:
        return isinstance(path, str) and "\x00" not in path and PurePosixPath(path).is_absolute() and ".." not in PurePosixPath(path).parts

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        responses = []
        with self._connection() as client, self._operation_lock:
            for path, content in files:
                if not self._valid_path(path):
                    responses.append(FileUploadResponse(path=path, error="invalid_path"))
                    continue
                try:
                    client.files.write(path, content)
                    responses.append(FileUploadResponse(path=path))
                except Exception as exc:
                    responses.append(FileUploadResponse(path=path, error=str(exc)))
        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses = []
        with self._connection() as client, self._operation_lock:
            for path in paths:
                if not self._valid_path(path):
                    responses.append(FileDownloadResponse(path=path, error="invalid_path"))
                    continue
                try:
                    content = bytearray()
                    signature = None
                    while True:
                        args = base64.b64encode(json.dumps([path, len(content), signature]).encode()).decode()
                        result = self._run(client, f"python3 -c {shlex.quote(_DOWNLOAD_SCRIPT)} {shlex.quote(args)}")
                        if result.exit_code:
                            raise RuntimeError(result.stderr or "File download command failed")
                        payload = json.loads(result.stdout)
                        if payload.get("error"):
                            raise RuntimeError(payload["error"])
                        signature = payload["signature"]
                        chunk = base64.b64decode(payload["data"], validate=True)
                        expected_size = min(_CHUNK_SIZE, signature[2] - len(content))
                        if len(chunk) != expected_size:
                            raise RuntimeError("Incomplete file download")
                        content.extend(chunk)
                        if len(content) == signature[2]:
                            break
                    responses.append(FileDownloadResponse(path=path, content=bytes(content)))
                except Exception as exc:
                    responses.append(FileDownloadResponse(path=path, error=str(exc)))
        return responses
