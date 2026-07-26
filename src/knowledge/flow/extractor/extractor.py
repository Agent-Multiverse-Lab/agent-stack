from __future__ import annotations

import asyncio
from collections.abc import Iterable
from importlib import import_module
from pathlib import Path
from typing import Any, BinaryIO

from .base import BaseExtractor, ExtractorResult, NoExtractorError

_DEFAULT_PROVIDER_ORDER = ("rapidocr", "paddleocr", "unlimitedocr")
_DEFAULT_PROVIDER_TYPES = {
    "rapidocr": (
        "src.knowledge.flow.extractor.rapid_ocr",
        "RapidOCRExtractor",
    ),
    "paddleocr": (
        "src.knowledge.flow.extractor.paddle_ocr",
        "PaddleOCRExtractor",
    ),
    "unlimitedocr": (
        "src.knowledge.flow.extractor.unlimited_ocr",
        "UnlimitedOCRExtractor",
    ),
}
_PROVIDER_ALIASES = {
    "rapid_ocr": "rapidocr",
    "paddle_ocr": "paddleocr",
    "unlimited_ocr": "unlimitedocr",
    "baidu_unlimited_ocr": "unlimitedocr",
}


class Extractor:
    """OCR 提取器的懒加载选择器，仅供 PDF 和图片解析器使用。"""

    def __init__(self, providers: Iterable[Any] | None = None) -> None:
        self._providers: dict[str, Any] = {}
        self._aliases: dict[str, str] = dict(_PROVIDER_ALIASES)
        self._locks: dict[str, asyncio.Lock] = {}
        self._use_defaults = providers is None
        self._order: list[str] = list(_DEFAULT_PROVIDER_ORDER) if self._use_defaults else []
        for provider in providers or ():
            self.register(provider)

    @classmethod
    def default(cls) -> Extractor:
        return cls()

    def register(self, provider: Any) -> None:
        canonical_name = self._normalize_name(self._provider_name(provider))
        canonical_name = _PROVIDER_ALIASES.get(canonical_name, canonical_name)
        if canonical_name in self._providers:
            raise ValueError(f"提取器已注册：{canonical_name}。")

        self._providers[canonical_name] = provider
        if canonical_name not in self._order:
            self._order.append(canonical_name)
        for alias in getattr(provider, "aliases", ()):
            normalized_alias = self._normalize_name(str(alias))
            existing = self._aliases.get(normalized_alias)
            if existing is not None and existing != canonical_name:
                raise ValueError(f"提取器别名已注册：{alias}。")
            self._aliases[normalized_alias] = canonical_name

    async def extractor_file(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
        extractor_type: str | None = None,
        content_type: str | None = None,
        **params: Any,
    ) -> ExtractorResult:
        selected_name = self._canonical_name(extractor_type) if extractor_type is not None else None
        if selected_name is not None:
            provider = await self._get_provider(selected_name)
            self._ensure_supported(provider, file_name, content_type)
            return await self._call_provider(
                provider,
                file_source,
                file_name=file_name,
                content_type=content_type,
                **params,
            )

        failures: list[str] = []
        supported_provider_seen = False
        for provider_name in self._order:
            try:
                provider = await self._get_provider(provider_name)
            except Exception as error:
                failures.append(f"{provider_name}：初始化失败（{type(error).__name__}）")
                continue

            if not provider.is_supported(
                Path(file_name).suffix,
                content_type=content_type,
            ):
                continue
            supported_provider_seen = True
            try:
                result = await self._call_provider(
                    provider,
                    file_source,
                    file_name=file_name,
                    content_type=content_type,
                    **params,
                )
            except Exception as error:
                failures.append(f"{self._provider_name(provider)}：调用失败（{type(error).__name__}）")
                continue

            if result.success and result.content.strip():
                return result
            failures.append(f"{result.extractor}：{result.error or '结果为空'}")

        if not supported_provider_seen and not failures:
            raise NoExtractorError(f"没有 OCR 提取器支持文件 {Path(file_name).name!r}，content_type={content_type!r}。")
        details = "；".join(failures) or "没有提供方返回内容"
        raise RuntimeError(f"所有 OCR 提取器均失败：{details}。")

    async def extract(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
        extractor_type: str | None = None,
        content_type: str | None = None,
        **params: Any,
    ) -> ExtractorResult:
        return await self.extractor_file(
            file_source,
            file_name=file_name,
            extractor_type=extractor_type,
            content_type=content_type,
            **params,
        )

    async def _get_provider(self, requested_name: str) -> Any:
        normalized_name = self._canonical_name(requested_name)
        provider = self._providers.get(normalized_name)
        if provider is not None:
            return provider
        if not self._use_defaults or normalized_name not in _DEFAULT_PROVIDER_TYPES:
            supported = ", ".join(sorted(set(self._order) | set(self._aliases)))
            raise NoExtractorError(f"不支持的提取器类型：{requested_name}。支持的提取器：{supported or '无'}。")

        lock = self._locks.setdefault(normalized_name, asyncio.Lock())
        async with lock:
            provider = self._providers.get(normalized_name)
            if provider is None:
                provider = await asyncio.to_thread(
                    _construct_default_provider,
                    normalized_name,
                )
                self._providers[normalized_name] = provider
            return provider

    async def _call_provider(
        self,
        provider: Any,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
        content_type: str | None,
        **params: Any,
    ) -> ExtractorResult:
        result = await provider.extractor_file(
            file_source,
            file_name=file_name,
            content_type=content_type,
            **params,
        )
        if isinstance(result, ExtractorResult):
            return result
        return ExtractorResult(
            extractor=str(result.extractor),
            file_path=str(result.file_path),
            content=str(result.content),
            success=bool(result.success),
            error=result.error,
            metadata=dict(result.metadata),
        )

    def _ensure_supported(
        self,
        provider: Any,
        file_name: str,
        content_type: str | None,
    ) -> None:
        if provider.is_supported(
            Path(file_name).suffix,
            content_type=content_type,
        ):
            return
        raise NoExtractorError(f"{self._provider_name(provider)} 不支持文件 {Path(file_name).name!r}，content_type={content_type!r}。")

    def _canonical_name(self, name: str) -> str:
        normalized_name = self._normalize_name(name)
        return self._aliases.get(normalized_name, normalized_name)

    @staticmethod
    def _normalize_name(name: str) -> str:
        normalized_name = name.strip().lower().replace("-", "_")
        if not normalized_name:
            raise ValueError("提取器名称不能为空。")
        return normalized_name

    @staticmethod
    def _provider_name(provider: Any) -> str:
        service_name = getattr(provider, "service_name", None)
        if callable(service_name):
            return str(service_name())
        return type(provider).__name__.removesuffix("Extractor").lower()


def _construct_default_provider(provider_name: str) -> BaseExtractor:
    module_name, class_name = _DEFAULT_PROVIDER_TYPES[provider_name]
    provider_type = getattr(import_module(module_name), class_name)
    return provider_type()


__all__ = ["Extractor"]
