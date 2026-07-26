from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, BinaryIO

from rapidocr import RapidOCR

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
RAPID_OCR_CALL_OPTIONS = (
    "use_det",
    "use_cls",
    "use_rec",
    "return_word_box",
    "return_single_char_box",
    "text_score",
    "box_thresh",
    "unclip_ratio",
)


class RapidOCRExtractor(BaseExtractor):
    """集成 RapidOCR，用于远程 API 不可用的情况。"""

    def __init__(
        self,
        *,
        config_path: str | Path | None = None,
        params: dict[str, Any] | None = None,
    ) -> None:
        self.config_path = config_path
        self.params = dict(params or {})
        self._ocr = RapidOCR(
            config_path=str(self.config_path) if self.config_path else None,
            params=self.params or None,
        )

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
                str(status.get("error") or "RapidOCR 不可用。"),
                status,
            )

        try:
            output = await asyncio.to_thread(
                self._run_rapidocr,
                file_source,
                params,
            )
        except Exception as exc:
            return _failure_result(
                self.service_name(),
                result_path,
                f"RapidOCR 提取失败：{exc}",
                {
                    "stage": "extract",
                    "exception_type": type(exc).__name__,
                },
            )

        lines = _extract_text_lines(output)
        scores = _extract_scores(output)
        return ExtractorResult(
            extractor=self.service_name(),
            file_path=result_path,
            content="\n".join(lines),
            success=True,
            metadata={
                "line_count": len(lines),
                "scores": scores,
                "average_score": _average_score(scores),
            },
        )

    async def check_status(self, **_: Any) -> dict[str, Any]:
        return {"available": True, "service": self.service_name()}

    def service_name(self) -> str:
        return "rapidocr"

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

    def _run_rapidocr(
        self,
        file_source: str | Path | bytes | BinaryIO,
        params: dict[str, Any],
    ) -> Any:
        call_options = {key: params[key] for key in RAPID_OCR_CALL_OPTIONS if key in params and params[key] is not None}
        if isinstance(file_source, (str, Path, bytes)):
            source = file_source
        else:
            source = file_source.read()
            if not isinstance(source, bytes):
                raise TypeError("file_source.read() 必须返回 bytes。")
        return self._ocr(source, **call_options)


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


def _result_file_path(
    file_source: str | Path | bytes | BinaryIO,
    file_name: str,
) -> str:
    if isinstance(file_source, (str, Path)):
        return str(file_source)
    return file_name


def _extract_text_lines(output: Any) -> list[str]:
    texts = getattr(output, "txts", None)
    if texts is None and isinstance(output, dict):
        texts = output.get("txts") or output.get("texts")
    if texts is None:
        return []
    return [str(text).strip() for text in texts if str(text).strip()]


def _extract_scores(output: Any) -> list[float]:
    scores = getattr(output, "scores", None)
    if scores is None and isinstance(output, dict):
        scores = output.get("scores")
    if scores is None:
        return []

    normalized_scores: list[float] = []
    for score in scores:
        try:
            normalized_scores.append(float(score))
        except (TypeError, ValueError):
            continue
    return normalized_scores


def _average_score(scores: list[float]) -> float | None:
    if not scores:
        return None
    return sum(scores) / len(scores)
