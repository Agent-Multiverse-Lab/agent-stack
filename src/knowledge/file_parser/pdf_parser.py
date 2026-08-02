from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO

from pypdf import PdfReader as pdf2_read

from .utils.parser_pdf_outline import extract_pdf_outline


class PdfParseError(RuntimeError):
    pass


class BasePdfParser(ABC):
    @abstractmethod
    async def __call__(
        self,
        file_source: str | Path | bytes | BinaryIO,
    ) -> object:
        """解析 PDF；具体解析过程由子类实现。"""


class PlainPdfParser(BasePdfParser):
    """只读取 PDF 原生文本层，不提取图片，也不执行 OCR。"""

    async def __call__(
        self,
        file_source: str | Path | bytes | BinaryIO,
    ) -> tuple[list[str], list[tuple[str, int, int]]]:
        try:
            if isinstance(file_source, (str, Path)):
                current_file_source: str | Path | BytesIO = file_source
                outline_source: str | Path | bytes = file_source
            elif isinstance(file_source, bytes):
                current_file_source = BytesIO(file_source)
                outline_source = file_source
            else:
                file_source.seek(0)
                content = file_source.read()
                if not isinstance(content, bytes):
                    raise TypeError("PDF file_source 文件流必须返回 bytes。")
                current_file_source = BytesIO(content)
                outline_source = content

            self.pdf = pdf2_read(current_file_source)
            lines: list[str] = []
            for page in self.pdf.pages:
                lines.extend((page.extract_text() or "").split("\n"))
            outlines = extract_pdf_outline(outline_source)
        except PdfParseError:
            raise
        except Exception as error:
            raise PdfParseError(f"PlainPdfParser failed with {type(error).__name__}.") from error
        return lines, outlines


class DoclingPdfParser:
    async def to_markdown(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str | None = None,
    ) -> str:
        try:
            markdown = await asyncio.to_thread(
                _convert_pdf_with_docling,
                file_source,
                file_name,
            )
        except PdfParseError:
            raise
        except Exception as error:
            raise PdfParseError(f"DoclingPdfParser failed with {type(error).__name__}.") from error

        if not markdown.strip():
            raise PdfParseError("DoclingPdfParser returned no content.")
        return markdown

    async def parse(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str | None = None,
        as_json: bool = False,
    ) -> str | dict[str, object]:
        markdown = await self.to_markdown(file_source, file_name=file_name)
        if as_json:
            return {"markdown": markdown}
        return markdown


class OcrPdfParser(BasePdfParser):
    def __init__(self, extractor: Any | None = None) -> None:
        if extractor is None:
            from src.knowledge.flow.extractor import PaddleOCRExtractor

            extractor = PaddleOCRExtractor()
        self.extractor = extractor

    async def to_markdown(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str | None = None,
        language: str = "ch",
        flatten_media_to_text: bool = True,
        remove_toc: bool = False,
        remove_footer: bool = False,
    ) -> str:
        markdown, _ = await self._extract_markdown(
            file_source,
            file_name=file_name,
            language=language,
            flatten_media_to_text=flatten_media_to_text,
            remove_toc=remove_toc,
            remove_footer=remove_footer,
        )
        return markdown

    async def __call__(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str | None = None,
        language: str = "ch",
        flatten_media_to_text: bool = True,
        remove_toc: bool = False,
        remove_footer: bool = False,
        as_json: bool = False,
    ) -> str | dict[str, object]:
        if not as_json:
            return await self.to_markdown(
                file_source,
                file_name=file_name,
                language=language,
                flatten_media_to_text=flatten_media_to_text,
                remove_toc=remove_toc,
                remove_footer=remove_footer,
            )
        markdown, metadata = await self._extract_markdown(
            file_source,
            file_name=file_name,
            language=language,
            flatten_media_to_text=flatten_media_to_text,
            remove_toc=remove_toc,
            remove_footer=remove_footer,
        )
        return {
            "markdown": markdown,
            "metadata": metadata,
        }

    async def _extract_markdown(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str | None,
        language: str,
        flatten_media_to_text: bool,
        remove_toc: bool,
        remove_footer: bool,
    ) -> tuple[str, dict[str, Any]]:
        if file_name is None:
            file_name = Path(file_source).name if isinstance(file_source, (str, Path)) else "document.pdf"
        result = await self.extractor.extractor_file(
            file_source,
            extractor_type="paddleocr",
            content_type="application/pdf",
            file_name=file_name,
            lang=language,
            flatten_media_to_text=flatten_media_to_text,
            remove_toc=remove_toc,
            remove_footer=remove_footer,
        )
        markdown = str(result.content).replace("\r\n", "\n").replace("\r", "\n")
        if not result.success or not markdown.strip():
            raise PdfParseError(result.error or "PaddleOCR returned no content.")
        return markdown, dict(result.metadata)


def _convert_pdf_with_docling(
    file_source: str | Path | bytes | BinaryIO,
    file_name: str | None,
) -> str:
    from docling.document_converter import DocumentConverter
    from docling_core.types.io import DocumentStream

    if isinstance(file_source, (str, Path)):
        source: str | Path | DocumentStream = file_source
    else:
        if isinstance(file_source, bytes):
            content = file_source
        else:
            file_source.seek(0)
            content = file_source.read()
            if not isinstance(content, bytes):
                raise TypeError("PDF file_source 文件流必须返回 bytes。")
        source = DocumentStream(
            name=file_name or "document.pdf",
            stream=BytesIO(content),
        )

    markdown = DocumentConverter().convert(source).document.export_to_markdown()
    return markdown.replace("\r\n", "\n").replace("\r", "\n").strip()
