from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import BinaryIO


class MarkdownParser:
    name = "md"

    async def parse(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        extensions: Sequence[str] = (),
        as_json: bool = False,
    ) -> str | dict[str, object]:
        text = await self.to_markdown(
            file_source,
            extensions=extensions,
        )
        return await self.parse_text(
            text,
            extensions=extensions,
            as_json=as_json,
        )

    async def to_markdown(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        extensions: Sequence[str] = (),
    ) -> str:
        text = await _read_text(file_source)
        return text.replace("\r\n", "\n").replace("\r", "\n")

    async def parse_text(
        self,
        text: str,
        *,
        extensions: Sequence[str] = (),
        as_json: bool = False,
    ) -> str | dict[str, object]:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        rendered, elements = await asyncio.to_thread(
            _render_markdown,
            text,
            tuple(extensions),
        )
        if not as_json:
            return text
        return {"markdown": text, "html": rendered, "elements": elements}


async def _read_text(
    file_source: str | Path | bytes | BinaryIO,
) -> str:
    if isinstance(file_source, bytes):
        content = file_source
    elif isinstance(file_source, (str, Path)):
        content = await asyncio.to_thread(Path(file_source).read_bytes)
    else:
        content = await asyncio.to_thread(file_source.read)
        if not isinstance(content, bytes):
            raise TypeError("file_source.read() 必须返回 bytes。")
    return content.decode("utf-8-sig")


def _render_markdown(
    text: str,
    extensions: tuple[str, ...],
) -> tuple[str, list[dict[str, object]]]:
    import markdown
    from bs4 import BeautifulSoup

    html = markdown.markdown(text, extensions=list(extensions))
    soup = BeautifulSoup(html, "html.parser")
    elements: list[dict[str, object]] = []
    for node in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table"]):
        if node.name.startswith("h"):
            elements.append(
                {
                    "type": "heading",
                    "level": int(node.name[1]),
                    "text": node.get_text(" ", strip=True),
                }
            )
        elif node.name == "table":
            table_rows = [[cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])] for row in node.find_all("tr")]
            elements.append({"type": "table", "rows": table_rows})
        else:
            elements.append(
                {
                    "type": "list_item" if node.name == "li" else "paragraph",
                    "text": node.get_text(" ", strip=True),
                }
            )
    return html, elements
