from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from typing import BinaryIO


class DocxParser:
    name = "docx"

    async def to_markdown(
        self,
        file_source: str | Path | bytes | BinaryIO,
    ) -> str:
        parsed = await asyncio.to_thread(
            _parse_with_python_docx,
            file_source,
        )
        return str(parsed["markdown"])

    async def parse(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        as_json: bool = False,
    ) -> str | dict[str, object]:
        parsed = await asyncio.to_thread(
            _parse_with_python_docx,
            file_source,
        )
        return parsed if as_json else str(parsed["markdown"])


class DoclingDocxParser:
    name = "docx"

    async def to_markdown(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
    ) -> str:
        parsed = await asyncio.to_thread(
            _parse_with_docling,
            file_source,
            file_name,
        )
        return str(parsed["markdown"])

    async def parse(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
        as_json: bool = False,
    ) -> str | dict[str, object]:
        parsed = await asyncio.to_thread(
            _parse_with_docling,
            file_source,
            file_name,
        )
        return parsed if as_json else str(parsed["markdown"])


def _parse_with_python_docx(
    file_source: str | Path | bytes | BinaryIO,
) -> dict[str, object]:
    from docx import Document
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    source = BytesIO(file_source) if isinstance(file_source, bytes) else file_source
    document = Document(source)
    markdown_parts: list[str] = []
    elements: list[dict[str, object]] = []
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            paragraph = Paragraph(child, document)
            text = paragraph.text.strip()
            if not text:
                continue
            style = paragraph.style.name if paragraph.style is not None else ""
            if style.startswith("Heading "):
                level_text = style.removeprefix("Heading ")
                level = int(level_text) if level_text.isdigit() else 1
                markdown_parts.append(f"{'#' * min(level, 6)} {text}")
                elements.append({"type": "heading", "level": level, "text": text})
            elif style.startswith("List"):
                markdown_parts.append(f"- {text}")
                elements.append({"type": "list_item", "text": text})
            else:
                markdown_parts.append(text)
                elements.append({"type": "paragraph", "text": text})
        elif isinstance(child, CT_Tbl):
            table = Table(child, document)
            rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
            if rows:
                markdown_parts.append(_markdown_table(rows))
                elements.append({"type": "table", "rows": rows})

    markdown = "\n\n".join(markdown_parts).strip()
    if not markdown:
        raise ValueError("python-docx returned no content.")
    return {"markdown": markdown, "elements": elements}


def _parse_with_docling(
    file_source: str | Path | bytes | BinaryIO,
    file_name: str,
) -> dict[str, object]:
    from docling.document_converter import DocumentConverter
    from docling_core.types.io import DocumentStream

    if isinstance(file_source, (str, Path)):
        source: Path | DocumentStream = Path(file_source)
    else:
        content = file_source if isinstance(file_source, bytes) else file_source.read()
        if not isinstance(content, bytes):
            raise TypeError("file_source.read() 必须返回 bytes。")
        source = DocumentStream(
            name=Path(file_name).name,
            stream=BytesIO(content),
        )

    markdown = DocumentConverter().convert(source).document.export_to_markdown().strip()
    if not markdown:
        raise ValueError("Docling returned no content.")
    return {"markdown": markdown}


def _markdown_table(rows: list[list[str]]) -> str:
    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]

    def line(values: list[str]) -> str:
        return "| " + " | ".join(value.replace("|", "\\|") for value in values) + " |"

    return "\n".join([line(padded[0]), line(["---"] * width), *(line(row) for row in padded[1:])])
