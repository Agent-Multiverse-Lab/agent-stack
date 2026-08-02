from __future__ import annotations

import asyncio
from mimetypes import guess_type
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import urlparse

from src.configs.config import config

from .base import BaseExtractor, ExtractorResult, NoExtractorError

SUPPORTED_CONTENT_TYPES = (
    "application/pdf",
    "image/*",
)
SUPPORTED_EXTENSIONS = (
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
)


class PaddleOCRExtractor(BaseExtractor):
    aliases = ("paddle_ocr",)

    def __init__(self) -> None:
        self.api_url = config.paddle_ocr_api_url.strip()
        self.api_key = config.paddle_ocr_api_key.strip()
        self.timeout_seconds = float(config.document_parser_api_timeout_seconds)

    async def extractor_file(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
        **params: Any,
    ) -> ExtractorResult:
        suffix = Path(file_name).suffix
        result_path = _result_file_path(file_source, file_name)
        if not self.is_supported(suffix, content_type=params.get("content_type")):
            raise NoExtractorError(f"{self.service_name()} 不支持文件 {Path(file_name).name!r}，content_type={params.get('content_type')!r}。")

        status = await self.check_status(**params)
        if not status.get("available"):
            return _failure_result(
                self.service_name(),
                result_path,
                str(status.get("error") or "PaddleOCR API 不可用。"),
                status,
            )

        try:
            payload = await _call_paddle_ocr_api(
                api_url=self.api_url,
                api_key=self.api_key,
                file_source=file_source,
                file_name=file_name,
                content_type=_resolve_content_type(
                    file_name,
                    content_type=params.get("content_type"),
                ),
                lang=str(params.get("lang", "ch")),
                timeout=self.timeout_seconds,
            )
        except ImportError as exc:
            return _dependency_failure_result(
                self.service_name(),
                result_path,
                exc,
            )
        except Exception as exc:
            return _failure_result(
                self.service_name(),
                result_path,
                f"PaddleOCR API 提取失败：{exc}",
                {
                    "stage": "extract",
                    "exception_type": type(exc).__name__,
                },
            )

        lines = _extract_text_lines(payload)
        return ExtractorResult(
            extractor=self.service_name(),
            file_path=result_path,
            content="\n".join(lines),
            success=True,
            metadata={"line_count": len(lines)},
        )

    async def check_status(self, **_: Any) -> dict[str, Any]:
        try:
            import httpx  # noqa: F401
        except ImportError as exc:
            return _dependency_status(self.service_name(), exc)

        if not self.api_key:
            return {
                "available": False,
                "service": self.service_name(),
                "error": "PaddleOCR API Key 未配置。",
                "stage": "api_check",
                "missing_config": "paddle_ocr_api_key",
            }

        return await _check_http_api(
            service_name="PaddleOCR",
            api_url=self.api_url,
            headers=_auth_headers(self.api_key),
            timeout=self.timeout_seconds,
            missing_config_key="paddle_ocr_api_url",
        )

    def service_name(self) -> str:
        return "paddleocr"

    def is_supported(
        self,
        file_suffix: str,
        *,
        content_type: str | None = None,
    ) -> bool:
        extension = file_suffix.lower()
        if extension and extension in SUPPORTED_EXTENSIONS:
            return True

        normalized_content_type = (content_type or "").lower().strip()
        for candidate in SUPPORTED_CONTENT_TYPES:
            if candidate == normalized_content_type:
                return True
            if candidate.endswith("/*") and normalized_content_type.startswith(candidate[:-1]):
                return True
        return False

    def get_supported_type(self) -> list[str]:
        return [*SUPPORTED_CONTENT_TYPES, *SUPPORTED_EXTENSIONS]


async def _call_paddle_ocr_api(
    *,
    api_url: str,
    api_key: str,
    file_source: str | Path | bytes | BinaryIO,
    file_name: str,
    content_type: str,
    lang: str,
    timeout: float,
) -> Any:
    import httpx

    headers = _auth_headers(api_key)
    file_bytes = await _read_file_source(file_source)
    files = {"file": (file_name, file_bytes, content_type)}
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            api_url,
            data={"lang": lang},
            files=files,
            headers=headers,
        )
    response.raise_for_status()
    return _decode_response(response)


async def _check_http_api(
    *,
    service_name: str,
    api_url: str,
    headers: dict[str, str],
    timeout: float,
    missing_config_key: str,
) -> dict[str, Any]:
    normalized_url = api_url.strip()
    if not normalized_url:
        return {
            "available": False,
            "service": service_name,
            "error": f"{service_name} API URL 未配置。",
            "stage": "api_check",
            "missing_config": missing_config_key,
        }

    parsed = urlparse(normalized_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {
            "available": False,
            "service": service_name,
            "error": f"{service_name} API URL 无效。",
            "stage": "api_check",
            "api_url": normalized_url,
            "reason": "invalid_url",
        }

    import httpx

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            try:
                response = await client.head(normalized_url, headers=headers)
            except httpx.RequestError:
                response = await client.get(normalized_url, headers=headers)
    except httpx.RequestError as exc:
        return {
            "available": False,
            "service": service_name,
            "error": f"{service_name} API 无法连接：{exc}",
            "stage": "api_check",
            "api_url": normalized_url,
            "exception_type": type(exc).__name__,
        }

    status_code = response.status_code
    if status_code < 400 or status_code == 405:
        return {"available": True, "service": service_name, "status_code": status_code}
    if status_code in {401, 403}:
        reason = "auth_invalid"
        error = f"{service_name} API 身份验证失败。"
    elif status_code == 404:
        reason = "endpoint_invalid"
        error = f"{service_name} API 端点不存在。"
    elif status_code >= 500:
        reason = "service_unavailable"
        error = f"{service_name} API 不可用。"
    else:
        reason = "unexpected_status"
        error = f"{service_name} API 状态检查失败，HTTP 状态码为 {status_code}。"

    return {
        "available": False,
        "service": service_name,
        "error": error,
        "stage": "api_check",
        "api_url": normalized_url,
        "status_code": status_code,
        "reason": reason,
    }


def _resolve_content_type(
    file_name: str,
    *,
    content_type: str | None = None,
) -> str:
    resolved = (content_type or "").lower().strip()
    if resolved:
        return resolved
    guessed, _ = guess_type(file_name)
    return guessed or "application/octet-stream"


def _auth_headers(api_key: str) -> dict[str, str]:
    if not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}


def _decode_response(response: Any) -> Any:
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        return response.json()
    try:
        return response.json()
    except ValueError:
        return response.text


def _extract_text_lines(payload: Any) -> list[str]:
    lines: list[str] = []
    _collect_text(payload, lines)
    return lines


def _collect_text(value: Any, lines: list[str]) -> None:
    if isinstance(value, str):
        if value.strip():
            lines.append(value.strip())
        return

    if isinstance(value, dict):
        for key in ("text", "rec_text", "content", "parsed_text"):
            text = value.get(key)
            if isinstance(text, str) and text.strip():
                lines.append(text.strip())
                return
        for key in ("lines", "pages", "result", "results", "data", "ocr_results"):
            if key in value:
                _collect_text(value[key], lines)
        return

    if isinstance(value, list):
        for item in value:
            _collect_text(item, lines)


def _failure_result(
    service_name: str,
    file_path: str,
    error: str,
    metadata: dict[str, Any],
) -> ExtractorResult:
    return ExtractorResult(
        extractor=service_name,
        file_path=file_path,
        success=False,
        error=error,
        metadata=metadata,
    )


def _dependency_status(service_name: str, exc: ImportError) -> dict[str, Any]:
    missing_dependency = exc.name or service_name
    return {
        "available": False,
        "service": service_name,
        "error": f"{service_name} 依赖未安装：{missing_dependency}。",
        "stage": "sdk_check",
        "missing_dependency": missing_dependency,
        "exception_type": type(exc).__name__,
    }


def _dependency_failure_result(
    service_name: str,
    file_path: str,
    exc: ImportError,
) -> ExtractorResult:
    status = _dependency_status(service_name, exc)
    return _failure_result(
        service_name,
        file_path,
        str(status["error"]),
        status,
    )


async def _read_file_source(
    file_source: str | Path | bytes | BinaryIO,
) -> bytes:
    if isinstance(file_source, bytes):
        return file_source
    if isinstance(file_source, (str, Path)):
        return await asyncio.to_thread(Path(file_source).read_bytes)

    content = await asyncio.to_thread(file_source.read)
    if not isinstance(content, bytes):
        raise TypeError("file_source.read() 必须返回 bytes。")
    return content


def _result_file_path(
    file_source: str | Path | bytes | BinaryIO,
    file_name: str,
) -> str:
    if isinstance(file_source, (str, Path)):
        return str(file_source)
    return file_name
