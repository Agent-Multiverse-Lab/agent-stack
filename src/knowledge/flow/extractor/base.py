from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO


class NoExtractorError(ValueError):
    """当没有 OCR 提取器能够处理文件时抛出。"""


@dataclass(slots=True, frozen=True)
class ExtractorResult:
    extractor: str
    file_path: str
    content: str = ""
    success: bool = True
    error: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class BaseExtractor(ABC):
    aliases: tuple[str, ...] = ()

    @abstractmethod
    async def extractor_file(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
        **params: Any,
    ) -> ExtractorResult:
        """从路径、bytes 或二进制流中提取 OCR 文本。"""

    @abstractmethod
    async def check_status(self, **params: Any) -> dict[str, Any]:
        """检查本地模型或远程 API 是否可用。"""

    def service_name(self) -> str:
        return type(self).__name__.removesuffix("Extractor").lower()

    @abstractmethod
    def is_supported(
        self,
        file_suffix: str,
        *,
        content_type: str | None = None,
    ) -> bool:
        """返回当前提取器是否支持该输入类型。"""

    @abstractmethod
    def get_supported_type(self) -> list[str]:
        """返回支持的 MIME 类型和文件后缀。"""


__all__ = [
    "BaseExtractor",
    "ExtractorResult",
    "NoExtractorError",
]
