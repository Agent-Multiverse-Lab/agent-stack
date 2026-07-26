from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from time import monotonic
from typing import Any, BinaryIO
from urllib.parse import urlparse

import httpx

from src.configs.config import config

from .base import BaseExtractor, ExtractorResult, NoExtractorError

SUPPORTED_CONTENT_TYPES = (
    "application/pdf",
    "image/*",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
)
SUPPORTED_EXTENSIONS = (
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".tif",
    ".tiff",
    ".ofd",
    ".doc",
    ".docx",
    ".txt",
    ".wps",
    ".ppt",
    ".pptx",
)
TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_LOCAL_DOCUMENT_BYTES = 50 * 1024 * 1024
RUNNING_STATUSES = {"pending", "running"}


class UnlimitedOCRExtractor(BaseExtractor):
    """通过百度智能云 Unlimited-OCR API 解析文档。"""

    aliases = ("unlimited_ocr", "baidu_unlimited_ocr")

    def __init__(self) -> None:
        self.api_url = config.unlimited_ocr_api_url.strip().rstrip("/")
        self.api_key = config.unlimited_ocr_api_key.strip()
        self.secret_key = config.unlimited_ocr_secret_key.strip()
        self.request_timeout_seconds = float(config.document_parser_api_timeout_seconds)
        self.poll_interval_seconds = float(config.unlimited_ocr_poll_interval_seconds)
        self.poll_timeout_seconds = float(config.unlimited_ocr_poll_timeout_seconds)

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

        status = await self.check_status()
        if not status.get("available"):
            return _failure_result(
                self.service_name(),
                result_path,
                str(status.get("error") or "Unlimited-OCR API 不可用。"),
                status,
            )

        task_id: str | None = None
        try:
            file_bytes = await _read_file_source(file_source)
            size_error = _validate_file_size(file_bytes, file_name)
            if size_error:
                return _failure_result(
                    self.service_name(),
                    result_path,
                    size_error,
                    {"stage": "validate"},
                )
            file_data = _encode_file(file_bytes)
            timeout = httpx.Timeout(self.request_timeout_seconds)
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
            ) as client:
                access_token = await _get_access_token(
                    client,
                    api_key=self.api_key,
                    secret_key=self.secret_key,
                )
                task_id = await _submit_task(
                    client,
                    api_url=self.api_url,
                    access_token=access_token,
                    file_data=file_data,
                    file_name=file_name,
                )
                result = await _wait_for_result(
                    client,
                    query_url=f"{self.api_url}/query",
                    access_token=access_token,
                    task_id=task_id,
                    poll_interval=self.poll_interval_seconds,
                    poll_timeout=self.poll_timeout_seconds,
                )
                markdown = await _download_markdown(
                    client,
                    str(result.get("markdown_url") or ""),
                )
        except Exception as exc:
            metadata: dict[str, Any] = {
                "stage": "extract",
                "exception_type": type(exc).__name__,
            }
            if task_id:
                metadata["task_id"] = task_id
            return _failure_result(
                self.service_name(),
                result_path,
                f"Unlimited-OCR API 解析失败：{exc}",
                metadata,
            )

        return ExtractorResult(
            extractor=self.service_name(),
            file_path=result_path,
            content=markdown,
            success=True,
            metadata={
                "task_id": task_id,
                "output_format": "markdown",
            },
        )

    async def check_status(self, **_: Any) -> dict[str, Any]:
        missing_config = [
            name
            for name, value in (
                ("unlimited_ocr_api_key", self.api_key),
                ("unlimited_ocr_secret_key", self.secret_key),
                ("unlimited_ocr_api_url", self.api_url),
            )
            if not value
        ]
        if missing_config:
            return {
                "available": False,
                "service": self.service_name(),
                "error": "Unlimited-OCR API 配置不完整。",
                "stage": "config_check",
                "missing_config": missing_config,
            }
        if not _is_http_url(self.api_url):
            return {
                "available": False,
                "service": self.service_name(),
                "error": "Unlimited-OCR API URL 无效。",
                "stage": "config_check",
                "api_url": self.api_url,
            }
        return {"available": True, "service": self.service_name()}

    def service_name(self) -> str:
        return "unlimitedocr"

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


async def _get_access_token(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    secret_key: str,
) -> str:
    try:
        response = await client.get(
            TOKEN_URL,
            params={
                "grant_type": "client_credentials",
                "client_id": api_key,
                "client_secret": secret_key,
            },
        )
    except httpx.RequestError as exc:
        raise RuntimeError("获取 access_token 请求失败") from exc
    payload = _decode_json_response(response, stage="获取 access_token")
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        error = payload.get("error_description") or payload.get("error")
        raise RuntimeError(str(error or "响应中缺少 access_token"))
    return access_token


async def _submit_task(
    client: httpx.AsyncClient,
    *,
    api_url: str,
    access_token: str,
    file_data: str,
    file_name: str,
) -> str:
    try:
        response = await client.post(
            api_url,
            params={"access_token": access_token},
            data={"file_data": file_data, "file_name": file_name},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    except httpx.RequestError as exc:
        raise RuntimeError("提交解析任务请求失败") from exc
    payload = _decode_api_response(response, stage="提交解析任务")
    result = payload.get("result")
    task_id = result.get("task_id") if isinstance(result, dict) else None
    if not isinstance(task_id, str) or not task_id:
        raise RuntimeError("提交响应中缺少 task_id")
    return task_id


async def _wait_for_result(
    client: httpx.AsyncClient,
    *,
    query_url: str,
    access_token: str,
    task_id: str,
    poll_interval: float,
    poll_timeout: float,
) -> dict[str, Any]:
    deadline = monotonic() + poll_timeout
    while True:
        try:
            response = await client.post(
                query_url,
                params={"access_token": access_token},
                data={"task_id": task_id},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.RequestError as exc:
            raise RuntimeError("查询解析任务请求失败") from exc
        payload = _decode_api_response(response, stage="查询解析任务")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("查询响应中缺少 result")

        status = str(result.get("status") or "").lower()
        if status == "success":
            return result
        if status == "failed":
            raise RuntimeError(str(result.get("task_error") or "解析任务失败"))
        if status not in RUNNING_STATUSES:
            raise RuntimeError(f"未知的解析任务状态：{status or '空'}")

        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError(f"解析任务在 {poll_timeout:g} 秒内未完成")
        await asyncio.sleep(min(poll_interval, remaining))


async def _download_markdown(
    client: httpx.AsyncClient,
    markdown_url: str,
) -> str:
    if not _is_http_url(markdown_url):
        raise RuntimeError("解析结果中缺少有效的 markdown_url")
    try:
        response = await client.get(markdown_url)
    except httpx.RequestError as exc:
        raise RuntimeError("下载 Markdown 请求失败") from exc
    if response.status_code >= 400:
        raise RuntimeError(f"下载 Markdown 失败，HTTP {response.status_code}")
    return response.text.strip()


def _decode_api_response(
    response: httpx.Response,
    *,
    stage: str,
) -> dict[str, Any]:
    payload = _decode_json_response(response, stage=stage)
    error_code = payload.get("error_code")
    if error_code not in (None, 0, "0"):
        error_message = payload.get("error_msg") or "未知 API 错误"
        raise RuntimeError(f"{stage}失败：{error_code} {error_message}")
    return payload


def _decode_json_response(
    response: httpx.Response,
    *,
    stage: str,
) -> dict[str, Any]:
    if response.status_code >= 400:
        raise RuntimeError(f"{stage}失败，HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"{stage}返回了非 JSON 响应") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{stage}返回了无效响应")
    return payload


def _encode_file(file_bytes: bytes) -> str:
    return base64.b64encode(file_bytes).decode("ascii")


def _validate_file_size(file_bytes: bytes, file_name: str) -> str | None:
    size = len(file_bytes)
    limit = MAX_IMAGE_BYTES if Path(file_name).suffix.lower() in IMAGE_EXTENSIONS else MAX_LOCAL_DOCUMENT_BYTES
    if size <= limit:
        return None
    return f"本地文件大小为 {size} 字节，超过 file_data 方式的 {limit} 字节限制；请改用 file_url。"


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


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
