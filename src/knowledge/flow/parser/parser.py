from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any, BinaryIO, Literal

from src.knowledge.file_parser import (
    DoclingDocxParser,
    DocParser,
    DocxParser,
    ExcelParser,
    HtmlParser,
    ImageParser,
    MarkdownParser,
    PptxParser,
    TextParser,
)
from src.knowledge.file_parser.pdf_parser import (
    OcrPdfParser,
    PdfParseError,
    PlainPdfParser,
)
from src.utils import logger

from ..types import BlockKind, DocumentBlock, ParsedDocument

_IMAGE_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
}
_PAGE_HEADING = re.compile(
    r"^(?:Page\s+|第\s*)(\d+)(?:\s*页)?$",
    re.IGNORECASE,
)


class ParseError(RuntimeError):
    pass


class Parser:
    """每种文档的处理方式由对应的私有方法负责。"""

    def __init__(
        self,
        *,
        parser_method: Literal["plain", "ocr"] = "plain",
    ) -> None:
        configs: dict[str, dict[str, Any]] = {
            "pdf": {
                "suffix": [".pdf"],
                "parser_method": parser_method,
                "language": "ch",
                "flatten_media_to_text": True,
                "remove_toc": False,
                "remove_footer": False,
            },
            "docx": {
                "suffix": [".docx"],
                "parser_method": "python-docx",
                "preserve_headings": True,
                "preserve_lists": True,
                "preserve_tables": True,
            },
            "doc": {
                "suffix": [".doc"],
                "remove_scripts": True,
                "preserve_links": True,
            },
            "markdown": {
                "suffix": [".md", ".markdown"],
                "extensions": ("tables",),
                "preserve_source": True,
            },
            "text": {
                "suffix": [".txt"],
                "encoding": "utf-8-sig",
                "normalize_newlines": True,
            },
            "excel": {
                "suffix": [".csv", ".xlsx"],
                "encoding": "utf-8-sig",
                "delimiter": None,
                "sheets": None,
                "first_row_as_header": True,
            },
            "pptx": {
                "suffix": [".pptx"],
                "preserve_slide_titles": True,
                "preserve_tables": True,
                "include_speaker_notes": False,
            },
            "image": {
                "suffix": [
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".webp",
                    ".bmp",
                    ".gif",
                    ".tif",
                    ".tiff",
                ],
                "parser_method": "rapidocr",
                "language": "ch",
                "detect_orientation": True,
                "preserve_line_breaks": True,
            },
            "html": {
                "suffix": [".html", ".htm"],
                "encoding": "utf-8-sig",
                "remove_scripts": True,
                "remove_navigation": False,
                "preserve_links": True,
            },
        }
        self._config = {suffix: config for config in configs.values() for suffix in config["suffix"]}

    async def _pdf(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
    ) -> tuple[str, object, dict[str, Any]]:
        suffix = Path(file_name).suffix.lower()
        config = self._config[suffix]
        parser_method = config.get("parser_method", "plain")
        if not isinstance(parser_method, str):
            raise TypeError("PDF parser_method 必须是字符串。")
        parser_method = parser_method.strip().lower()

        if parser_method == "plain":
            parser = PlainPdfParser()
            lines, outlines = await parser(file_source)
            intermediate: list[dict[str, object]] = []
            for raw_line in lines:
                line = raw_line.strip()
                if not line:
                    continue
                intermediate.append(
                    {
                        "text": line,
                        "layout_type": "",
                        "doc_type_kwd": "text",
                        "position": [],
                        "image": None,
                    }
                )
            markdown = _pdf_to_markdown(intermediate, config)
            json_result = [dict(item) for item in intermediate]
        elif parser_method == "ocr":
            parser = OcrPdfParser()
            markdown = await parser.to_markdown(
                file_source,
                file_name=file_name,
                language=str(config.get("language", "ch")),
                flatten_media_to_text=bool(config.get("flatten_media_to_text", True)),
                remove_toc=bool(config.get("remove_toc", False)),
                remove_footer=bool(config.get("remove_footer", False)),
            )
            json_result = None
            outlines = []
        else:
            raise ValueError("PDF parser_method 只支持 'plain' 或 'ocr'。")

        return (
            markdown,
            parser,
            {
                "parser_method": parser_method,
                "ocr": parser_method == "ocr",
                "_json_result": json_result,
                "_outlines": outlines,
            },
        )

    async def _doc(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
    ) -> tuple[str, object, dict[str, Any]]:
        suffix = Path(file_name).suffix.lower()
        config = self._config[suffix]
        parser = DocParser()
        intermediate = _require_dict(
            await parser.parse(file_source, as_json=True),
            "DocParser",
        )
        return _doc_to_markdown(intermediate, config), parser, {}

    async def _docx(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
    ) -> tuple[str, object, dict[str, Any]]:
        suffix = Path(file_name).suffix.lower()
        config = self._config[suffix]
        parser_method = config.get("parser_method", "python-docx")
        if not isinstance(parser_method, str):
            raise TypeError("DOCX parser_method 必须是字符串。")
        parser_method = parser_method.strip().lower()

        if parser_method == "python-docx":
            parser = DocxParser()
            markdown = await parser.to_markdown(file_source)
        elif parser_method == "docling":
            parser = DoclingDocxParser()
            markdown = await parser.to_markdown(
                file_source,
                file_name=file_name,
            )
        else:
            raise ValueError("DOCX parser_method 只支持 'python-docx' 或 'docling'。")
        return markdown, parser, {"parser_method": parser_method}

    async def _markdown(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
    ) -> tuple[str, object, dict[str, Any]]:
        suffix = Path(file_name).suffix.lower()
        config = self._config[suffix]
        parser = MarkdownParser()
        markdown = await parser.to_markdown(
            file_source,
            extensions=_markdown_extensions(config),
        )
        return markdown, parser, {}

    async def _text(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
    ) -> tuple[str, object, dict[str, Any]]:
        suffix = Path(file_name).suffix.lower()
        config = self._config[suffix]
        parser = TextParser()
        intermediate = _require_dict(
            await parser.parse(
                file_source,
                encoding=str(config.get("encoding", "utf-8-sig")),
                as_json=True,
            ),
            "TextParser",
        )
        return str(intermediate.get("text") or ""), parser, {}

    async def _excel(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
    ) -> tuple[str, object, dict[str, Any]]:
        suffix = Path(file_name).suffix.lower()
        config = self._config[suffix]
        parser = ExcelParser()
        markdown = await parser.to_markdown(
            file_source,
            file_name=file_name,
            encoding=str(config.get("encoding", "utf-8-sig")),
            delimiter=config.get("delimiter"),
            sheets=config.get("sheets"),
        )
        return markdown, parser, {}

    async def _pptx(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
    ) -> tuple[str, object, dict[str, Any]]:
        suffix = Path(file_name).suffix.lower()
        config = self._config[suffix]
        parser = PptxParser()
        intermediate = _require_dict(
            await parser.parse(
                file_source,
                file_name=file_name,
                as_json=True,
            ),
            "PptxParser",
        )
        return _pptx_to_markdown(intermediate, config), parser, {}

    async def _html(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
    ) -> tuple[str, object, dict[str, Any]]:
        suffix = Path(file_name).suffix.lower()
        config = self._config[suffix]
        parser = HtmlParser()
        markdown = await parser.to_markdown(
            file_source,
            encoding=str(config.get("encoding", "utf-8-sig")),
        )
        return markdown, parser, {}

    async def _image(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
    ) -> tuple[str, object, dict[str, Any]]:
        suffix = Path(file_name).suffix.lower()
        config = self._config[suffix]
        parser_method = config.get("parser_method", "rapidocr")
        if not isinstance(parser_method, str):
            raise TypeError("图片 parser_method 必须是字符串。")
        parser_method = parser_method.strip().lower()

        if parser_method not in {"rapidocr", "paddleocr", "unlimitedocr"}:
            raise ValueError("图片 parser_method 只支持 'rapidocr'、'paddleocr' 或 'unlimitedocr'。")

        parser = ImageParser()
        intermediate = _require_dict(
            await parser.parse(
                file_source,
                file_name=file_name,
                extractor_type=parser_method,
                content_type=None,
                language=str(config.get("language", "ch")),
                detect_orientation=bool(config.get("detect_orientation", True)),
                as_json=True,
            ),
            "ImageParser",
        )
        lines = intermediate.get("lines")
        if not isinstance(lines, list):
            raise ParseError("ImageParser 的中间态缺少 lines。")
        separator = "\n" if config.get("preserve_line_breaks", True) else " "
        markdown = separator.join(str(line) for line in lines)
        return (
            markdown,
            parser,
            {"parser_method": parser_method},
        )

    async def parse(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
    ) -> ParsedDocument:
        name, suffix = _resolve_file_name(file_name)
        handlers = {
            ".pdf": self._pdf,
            ".doc": self._doc,
            ".docx": self._docx,
            ".md": self._markdown,
            ".markdown": self._markdown,
            ".txt": self._text,
            ".csv": self._excel,
            ".xlsx": self._excel,
            ".pptx": self._pptx,
            ".html": self._html,
            ".htm": self._html,
            **{image_suffix: self._image for image_suffix in _IMAGE_SUFFIXES},
        }
        handler = handlers.get(suffix)
        if handler is None:
            supported = ", ".join(sorted(handlers))
            logger.warning(
                "Parser 不支持文件后缀：file_name=%s suffix=%s",
                name,
                suffix,
            )
            raise ValueError(f"不支持的文件后缀：{suffix!r}。支持的后缀：{supported}。")

        logger.info(
            "Parser 分派处理器：file_name=%s suffix=%s handler=%s",
            name,
            suffix,
            handler.__name__,
        )
        source = "filename" if isinstance(file_source, (str, Path)) else "byte_stream"
        markdown, parser, parser_metadata = await handler(
            file_source,
            file_name=name,
        )
        parser_metadata = dict(parser_metadata)
        json_result = parser_metadata.pop("_json_result", None)
        outlines = parser_metadata.pop("_outlines", [])

        markdown = _normalize_markdown(markdown, parser)
        config = self._config[suffix]
        blocks = await _markdown_blocks(
            markdown,
            extensions=_markdown_extensions(config),
            body_kind="image" if suffix in _IMAGE_SUFFIXES else "text",
        )
        metadata: dict[str, Any] = {
            "parser": _parser_name(suffix),
            "parser_class": type(parser).__name__,
            "intermediate_format": "markdown",
            "source": source,
            "parser_config": deepcopy(config),
            **parser_metadata,
        }
        document = ParsedDocument(
            name=name,
            suffix=suffix,
            blocks=blocks,
            metadata=metadata,
            markdown=markdown,
            json_result=json_result,
            file_source=file_source if suffix == ".pdf" else None,
            outlines=outlines,
        )
        logger.info(
            "Parser 解析完成：file_name=%s suffix=%s parser=%s blocks=%s",
            name,
            suffix,
            type(parser).__name__,
            len(blocks),
        )
        return document


def _require_dict(value: object, parser_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ParseError(f"{parser_name} 的中间态必须是 dict。")
    return value


def _require_json_items(
    value: object,
    parser_name: str,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ParseError(f"{parser_name} 的中间态必须是 JSON list。")
    return value


def _normalize_markdown(markdown: object, parser: object) -> str:
    if not isinstance(markdown, str):
        raise ParseError(f"{type(parser).__name__} 的 Markdown 结果必须是字符串。")
    return markdown.replace("\r\n", "\n").replace("\r", "\n")


def _pdf_to_markdown(
    value: Sequence[dict[str, Any]],
    config: dict[str, Any],
) -> str:
    lines = [str(item.get("text") or "").strip() for item in value]
    lines = [line for line in lines if line]
    if config.get("remove_toc"):
        lines = [line for line in lines if not _looks_like_toc(line)]
    return "\n".join(lines)


def _doc_to_markdown(
    value: dict[str, object],
    config: dict[str, Any],
) -> str:
    html = str(value.get("html") or "")
    if not html:
        return str(value.get("text") or "")

    from markdownify import markdownify

    return markdownify(
        html,
        heading_style="ATX",
        strip=["a"] if not config.get("preserve_links", True) else None,
    ).strip()


def _pptx_to_markdown(
    value: dict[str, object],
    config: dict[str, Any],
) -> str:
    slides = value.get("slides")
    if not isinstance(slides, list):
        raise ParseError("PptxParser 的中间态缺少 slides。")
    sections: list[str] = []
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        heading = f"# 幻灯片 {slide.get('position')}"
        title = str(slide.get("title") or "")
        if title and config.get("preserve_slide_titles", True):
            heading += f"：{title}"
        lines = [heading]
        elements = slide.get("elements")
        for element in elements if isinstance(elements, list) else ():
            if not isinstance(element, dict):
                continue
            if element.get("type") == "table":
                rows = element.get("rows")
                if config.get("preserve_tables", True) and isinstance(rows, list) and rows:
                    lines.extend(["", _markdown_table(rows)])
            else:
                text = str(element.get("text") or "").strip()
                if text:
                    lines.append(text)
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


async def _markdown_blocks(
    markdown: str,
    *,
    extensions: Sequence[str],
    body_kind: BlockKind,
) -> list[DocumentBlock]:
    parsed = await MarkdownParser().parse_text(
        markdown,
        extensions=extensions,
        as_json=True,
    )
    elements = parsed.get("elements", [])
    if not isinstance(elements, list):
        raise ParseError("MarkdownParser 返回的 elements 必须是列表。")

    blocks: list[DocumentBlock] = []
    current_page: int | None = None
    for element in elements:
        if not isinstance(element, dict):
            continue
        element_type = str(element.get("type") or "")
        text = str(element.get("text") or "").strip()
        if element_type == "heading":
            page = _page_number(text)
            if page is not None:
                current_page = page
            elif text:
                blocks.append(
                    DocumentBlock(
                        text=text,
                        kind="title",
                        heading_level=int(element.get("level") or 1),
                        metadata=_block_metadata("heading", current_page),
                    )
                )
        elif element_type == "table":
            rows = element.get("rows")
            if isinstance(rows, list) and rows:
                blocks.append(
                    DocumentBlock(
                        text=_markdown_table(rows),
                        kind="table",
                        metadata=_block_metadata("table", current_page),
                    )
                )
        elif text:
            blocks.append(
                DocumentBlock(
                    text=text,
                    kind=body_kind,
                    metadata=_block_metadata(
                        element_type or "paragraph",
                        current_page,
                    ),
                )
            )
    if not blocks and markdown.strip():
        blocks.append(
            DocumentBlock(
                text=markdown.strip(),
                kind=body_kind,
            )
        )
    return blocks


def _remove_repeated_footers(
    pages: list[dict[str, object]],
) -> None:
    candidates: list[str] = []
    for page in pages:
        lines = [line.strip() for line in str(page["text"]).splitlines() if line.strip()]
        if len(lines) > 1:
            candidates.append(lines[-1])

    repeated = {text for text, count in Counter(candidates).items() if count >= 2}
    for page in pages:
        lines = str(page["text"]).splitlines()
        if lines and lines[-1].strip() in repeated:
            page["text"] = "\n".join(lines[:-1]).rstrip()


def _looks_like_toc(text: str) -> bool:
    first_line = next(
        (line.strip() for line in text.splitlines() if line.strip()),
        "",
    )
    return first_line.lower() in {"目录", "目 录", "table of contents"}


def _markdown_extensions(config: dict[str, Any]) -> tuple[str, ...]:
    extensions = config.get("extensions", ["tables"])
    requested = [extensions] if isinstance(extensions, str) else extensions
    if not isinstance(requested, Sequence):
        raise TypeError("extensions 必须是字符串或字符串序列。")
    return tuple(dict.fromkeys(["tables", *(str(extension) for extension in requested)]))


def _markdown_table(rows: Sequence[Sequence[object]]) -> str:
    width = max(len(row) for row in rows)
    padded = [list(row) + [""] * (width - len(row)) for row in rows]

    def line(values: Sequence[object]) -> str:
        escaped = (str(value if value is not None else "").replace("|", "\\|").replace("\n", "<br>") for value in values)
        return "| " + " | ".join(escaped) + " |"

    return "\n".join(
        [
            line(padded[0]),
            line(["---"] * width),
            *(line(row) for row in padded[1:]),
        ]
    )


def _block_metadata(
    element_type: str,
    page: int | None,
) -> dict[str, object]:
    metadata: dict[str, object] = {"element_type": element_type}
    if page is not None:
        metadata["page"] = page
    return metadata


def _page_number(text: str) -> int | None:
    matched = _PAGE_HEADING.fullmatch(text)
    return int(matched.group(1)) if matched is not None else None


def _parser_name(suffix: str) -> str:
    if suffix in {".csv", ".xlsx"}:
        return "excel"
    if suffix in _IMAGE_SUFFIXES:
        return "image"
    if suffix in {".md", ".markdown"}:
        return "markdown"
    return suffix.removeprefix(".")


def _resolve_file_name(file_name: str) -> tuple[str, str]:
    name = Path(file_name).name
    if not name:
        raise ValueError("file_name 不能为空。")
    suffix = Path(name).suffix.lower()
    if not suffix:
        raise ValueError("file_name 必须包含文件后缀。")
    return name, suffix


__all__ = [
    "ParseError",
    "Parser",
    "PdfParseError",
]
