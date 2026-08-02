from __future__ import annotations

import base64
import posixpath
import shlex

from agent_sandbox import Sandbox as AgentSandboxClient
from agent_sandbox.core.api_error import ApiError
from deepagents.backends.protocol import (
    FILE_NOT_FOUND,
    INVALID_PATH,
    IS_DIRECTORY,
    PERMISSION_DENIED,
    EditResult,
    ExecuteResponse,
    FileDownloadResponse,
    FileInfo,
    FileUploadResponse,
    GlobResult,
    GrepMatch,
    GrepResult,
    LsResult,
    ReadResult,
    WriteResult,
)
from deepagents.backends.sandbox import BaseSandbox

DEFAULT_EXECUTE_TIMEOUT = 120
MAX_EXECUTE_OUTPUT_BYTES = 100_000


class CustomSandbox(BaseSandbox):
    """基于 Agent Sandbox 实现 DeepAgents 的沙箱后端。"""

    def __init__(
        self,
        thread_id: str,
        uid: str,
        sandbox_url: str,
        **keywords: object,
    ) -> None:
        sandbox_id = str(keywords.pop("sandbox_id", uid)).strip()
        headers = keywords.pop("headers", None)
        execute_timeout = keywords.pop("execute_timeout", DEFAULT_EXECUTE_TIMEOUT)
        self._validate_init_params(
            thread_id=thread_id,
            uid=uid,
            sandbox_id=sandbox_id,
            sandbox_url=sandbox_url,
        )
        if headers is not None and not isinstance(headers, dict):
            raise TypeError("headers 必须是 dict[str, str]")

        self._id = sandbox_id
        self._thread_id = thread_id
        self._uid = uid
        self._sandbox_url = sandbox_url.rstrip("/")
        self._execute_timeout = int(execute_timeout)
        self.client = self._build_client(
            self._sandbox_url,
            headers={str(key): str(value) for key, value in headers.items()}
            if isinstance(headers, dict)
            else None,
        )

    @property
    def id(self) -> str:
        return self._id

    def _build_client(
        self,
        sandbox_url: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> AgentSandboxClient:
        """创建连接远程 Agent Box 的客户端。"""
        return AgentSandboxClient(
            base_url=sandbox_url,
            headers=headers,
            timeout=self._execute_timeout,
        )

    @staticmethod
    def _validate_init_params(**params) -> None:
        empty_params = [
            name
            for name, value in params.items()
            if value is None or (isinstance(value, str) and not value.strip())
        ]
        if empty_params:
            names = ", ".join(empty_params)
            raise ValueError(f"CustomSandbox 初始化参数不能为空: {names}")

    def execute(
        self,
        command: str,
        *,
        timeout: int | None = None,
    ) -> ExecuteResponse:
        if not command:
            return ExecuteResponse(
                output="Error: Command must be a non-empty string.",
                exit_code=1,
            )

        effective_timeout = timeout or self._execute_timeout
        try:
            response = self.client.shell.exec_command(
                command=command,
                timeout=effective_timeout,
                hard_timeout=effective_timeout,
                truncate=False,
            )
        except Exception as exc:  # noqa: BLE001
            return ExecuteResponse(
                output=f"Error executing command ({type(exc).__name__}): {exc}",
                exit_code=1,
            )

        data = getattr(response, "data", None)
        if data is None:
            message = getattr(response, "message", None) or "Sandbox returned no command data."
            return ExecuteResponse(output=f"Error: {message}", exit_code=1)

        output = str(getattr(data, "output", "") or "")
        exit_code = getattr(data, "exit_code", None)
        exit_code = int(exit_code) if exit_code is not None else None

        truncated_output, truncated = self._truncate_output(output or "<no output>")
        return ExecuteResponse(
            output=truncated_output,
            exit_code=exit_code,
            truncated=truncated,
        )

    def ls(self, path: str) -> LsResult:
        """通过 Agent Box 文件 API 列出目录。"""
        try:
            response = self.client.file.list_path(
                path=path,
                recursive=False,
                include_size=True,
            )
            entries: list[FileInfo] = []
            for entry in response.data.files or []:
                info: FileInfo = {
                    "path": entry.path,
                    "is_dir": bool(entry.is_directory),
                }
                if isinstance(entry.size, int):
                    info["size"] = entry.size
                if entry.modified_time:
                    info["modified_at"] = str(entry.modified_time)
                entries.append(info)
            return LsResult(entries=entries)
        except Exception as exc:  # noqa: BLE001
            return LsResult(error=str(exc) or f"Failed to list '{path}'")

    def read(
        self,
        file_path: str,
        offset: int = 0,
        limit: int = 2000,
    ) -> ReadResult:
        """通过 Agent Box 文件 API 分页读取文件。"""
        try:
            response = self.client.file.read_file(
                file=file_path,
                start_line=max(0, offset),
                end_line=max(0, offset) + limit,
            )
            content = response.data.content or ""
            encoding = str(getattr(response.data, "encoding", "") or "utf-8")
            if isinstance(content, bytes):
                content = base64.b64encode(content).decode("ascii")
                encoding = "base64"
            return ReadResult(
                file_data={"content": str(content), "encoding": encoding}
            )
        except Exception as exc:  # noqa: BLE001
            return ReadResult(error=str(exc) or f"Failed to read '{file_path}'")

    def write(self, file_path: str, content: str) -> WriteResult:
        """通过 Agent Box 文件 API 写入 UTF-8 文本。"""
        try:
            response = self.client.file.write_file(
                file=file_path,
                content=content,
                encoding="utf-8",
            )
            if getattr(response, "success", None) is False:
                return WriteResult(
                    error=str(getattr(response, "message", "") or INVALID_PATH)
                )
            return WriteResult(path=file_path)
        except Exception as exc:  # noqa: BLE001
            return WriteResult(error=str(exc) or f"Failed to write '{file_path}'")

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        """通过 Agent Box 文件 API 替换文本。"""
        if not old_string:
            return EditResult(error="old_string must not be empty")
        try:
            current = self.client.file.read_file(file=file_path).data
            current_content = current.content or ""
            if str(getattr(current, "encoding", "")).lower() == "base64":
                current_content = base64.b64decode(current_content).decode("utf-8")
            count = str(current_content).count(old_string)
            if count == 0:
                return EditResult(error=f"String not found in file: '{old_string}'")
            if count > 1 and not replace_all:
                return EditResult(
                    error="old_string appears multiple times; use replace_all=True"
                )

            response = self.client.file.str_replace_editor(
                command="str_replace",
                path=file_path,
                old_str=old_string,
                new_str=new_string,
                replace_mode="ALL" if replace_all else "FIRST",
            )
            if getattr(response, "success", None) is False:
                return EditResult(
                    error=str(getattr(response, "message", "") or INVALID_PATH)
                )
            return EditResult(
                path=file_path,
                occurrences=count if replace_all else 1,
            )
        except Exception as exc:  # noqa: BLE001
            return EditResult(error=str(exc) or f"Failed to edit '{file_path}'")

    def grep(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
    ) -> GrepResult:
        """通过远端 execute 搜索文件内容。"""
        search_path = path or "."
        include = f" --include={shlex.quote(glob)}" if glob else ""
        command = (
            f"grep -RFnH{include} -- {shlex.quote(pattern)} "
            f"{shlex.quote(search_path)}"
        )
        result = self.execute(command)
        if result.exit_code == 1:
            return GrepResult(matches=[])
        if result.exit_code not in (0, None):
            return GrepResult(error=result.output or "grep failed")

        matches: list[GrepMatch] = []
        for line in result.output.splitlines():
            parts = line.split(":", 2)
            if len(parts) != 3 or not parts[1].isdigit():
                continue
            matches.append(
                {"path": parts[0], "line": int(parts[1]), "text": parts[2]}
            )
        return GrepResult(matches=matches)

    def glob(self, pattern: str, path: str | None = None) -> GlobResult:
        """通过 Agent Box 文件 API 匹配路径。"""
        search_path = path or "/"
        try:
            response = self.client.file.find_files(
                path=search_path,
                glob=pattern,
            )
            matches: list[FileInfo] = [
                {"path": file_path} for file_path in response.data.files or []
            ]
            return GlobResult(matches=matches)
        except Exception as exc:  # noqa: BLE001
            return GlobResult(error=str(exc) or f"Failed to glob '{search_path}'")

    def read_file_base64(self, content_base64: str) -> ExecuteResponse:
        """在沙箱内解码 base64 内容并输出 UTF-8 文本。"""
        if not isinstance(content_base64, str) or not content_base64.strip():
            return ExecuteResponse(
                output="Error: Base64 content must be a non-empty string.",
                exit_code=1,
            )

        script = (
            "import base64, sys; "
            "pass_bytes = base64.b64decode(sys.argv[1], validate=True); "
            "print(pass_bytes.decode('utf-8'))"
        )
        command = (
            f"python3 -c {shlex.quote(script)} "
            f"{shlex.quote(content_base64.strip())}"
        )
        return self.execute(command)

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        responses: list[FileUploadResponse] = []
        for path, content in files:
            if not self._is_absolute_file_path(path):
                responses.append(FileUploadResponse(path=path, error=INVALID_PATH))
                continue

            try:
                parent = posixpath.dirname(path.rstrip("/")) or "/"
                mkdir = self.execute(f"mkdir -p {shlex.quote(parent)}")
                if mkdir.exit_code not in (0, None):
                    responses.append(FileUploadResponse(path=path, error=INVALID_PATH))
                    continue

                encoded = base64.b64encode(content).decode("ascii")
                response = self.client.file.write_file(
                    file=path,
                    content=encoded,
                    encoding="base64",
                )
                if getattr(response, "success", None) is False:
                    responses.append(
                        FileUploadResponse(
                            path=path,
                            error=str(getattr(response, "message", "") or INVALID_PATH),
                        )
                    )
                    continue
                responses.append(FileUploadResponse(path=path))
            except ApiError as exc:
                responses.append(
                    FileUploadResponse(path=path, error=self._upload_error(exc))
                )
            except Exception:
                responses.append(FileUploadResponse(path=path, error=INVALID_PATH))
        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses: list[FileDownloadResponse] = []
        for path in paths:
            if not self._is_absolute_file_path(path):
                responses.append(FileDownloadResponse(path=path, error=INVALID_PATH))
                continue

            try:
                check = self.execute(
                    "if [ -d {path} ]; then exit 3; fi; "  # noqa: UP032
                    "if [ ! -e {path} ]; then exit 2; fi; "
                    "if [ ! -f {path} ]; then exit 4; fi".format(
                        path=shlex.quote(path)
                    )
                )
                if check.exit_code == 2:
                    responses.append(
                        FileDownloadResponse(path=path, error=FILE_NOT_FOUND)
                    )
                    continue
                if check.exit_code == 3:
                    responses.append(FileDownloadResponse(path=path, error=IS_DIRECTORY))
                    continue
                if check.exit_code not in (0, None):
                    responses.append(FileDownloadResponse(path=path, error=INVALID_PATH))
                    continue

                content = b"".join(self.client.file.download_file(path=path))
                responses.append(FileDownloadResponse(path=path, content=content))
            except ApiError as exc:
                responses.append(
                    FileDownloadResponse(path=path, error=self._download_error(exc))
                )
            except Exception:
                responses.append(FileDownloadResponse(path=path, error=INVALID_PATH))
        return responses

    @staticmethod
    def _is_absolute_file_path(path: str) -> bool:
        return isinstance(path, str) and path.startswith("/") and path != "/"

    @staticmethod
    def _join_output(stdout: str, stderr: str) -> str:
        parts = []
        if stdout:
            parts.append(stdout)
        if stderr:
            parts.append("\n".join(f"[stderr] {line}" for line in stderr.splitlines()))
        return "\n".join(parts)

    @staticmethod
    def _append_line(output: str, line: str) -> str:
        return f"{output.rstrip()}\n{line}" if output else line

    @staticmethod
    def _truncate_output(output: str) -> tuple[str, bool]:
        raw = output.encode("utf-8")
        if len(raw) <= MAX_EXECUTE_OUTPUT_BYTES:
            return output, False
        truncated = raw[:MAX_EXECUTE_OUTPUT_BYTES].decode("utf-8", errors="ignore")
        return (
            f"{truncated}\n\n... Output truncated at {MAX_EXECUTE_OUTPUT_BYTES} bytes.",
            True,
        )

    @staticmethod
    def _upload_error(exc: ApiError) -> str:
        if exc.status_code == 403:
            return PERMISSION_DENIED
        return INVALID_PATH

    @staticmethod
    def _download_error(exc: ApiError) -> str:
        if exc.status_code == 404:
            return FILE_NOT_FOUND
        if exc.status_code == 403:
            return PERMISSION_DENIED
        return INVALID_PATH
