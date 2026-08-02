from __future__ import annotations

from pathlib import Path
from typing import Any, BinaryIO

from src.knowledge.flow.extractor import Extractor


class ImageParser:
    name = "image"

    def __init__(self, factory: Extractor | None = None) -> None:
        self.factory = factory or Extractor.default()

    async def parse(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
        extractor_type: str | None = None,
        content_type: str | None = None,
        language: str = "ch",
        detect_orientation: bool = True,
        as_json: bool = False,
    ) -> str | dict[str, object]:
        if extractor_type is not None:
            result = await self.factory.extractor_file(
                file_source,
                file_name=file_name,
                extractor_type=extractor_type,
                content_type=content_type,
                lang=language,
                detect_orientation=detect_orientation,
            )
            if not result.success or not result.content.strip():
                raise RuntimeError(result.error or f"{extractor_type} returned no content.")
            return _format_result(result, as_json)

        result = await self.factory.extractor_file(
            file_source,
            file_name=file_name,
            content_type=content_type,
            lang=language,
            detect_orientation=detect_orientation,
        )
        if not result.success or not result.content.strip():
            raise RuntimeError(result.error or "All image OCR extractors failed.")
        return _format_result(result, as_json)


def _format_result(result: Any, as_json: bool) -> str | dict[str, object]:
    if not as_json:
        return str(result.content)
    return {
        "lines": str(result.content).splitlines(),
        "metadata": dict(result.metadata),
    }
