from __future__ import annotations

import asyncio
from pathlib import Path
from typing import BinaryIO


class HtmlParser:
    name = "html"

    async def to_markdown(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        encoding: str = "utf-8-sig",
    ) -> str:
        markdown, _, _ = await _parse_html_file(file_source, encoding=encoding)
        return markdown

    async def parse(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        encoding: str = "utf-8-sig",
        as_json: bool = False,
    ) -> str | dict[str, object]:
        markdown, cleaned_html, elements = await _parse_html_file(
            file_source,
            encoding=encoding,
        )
        if not as_json:
            return markdown
        return {
            "markdown": markdown,
            "html": cleaned_html,
            "elements": elements,
        }


async def _parse_html_file(
    file_source: str | Path | bytes | BinaryIO,
    *,
    encoding: str,
) -> tuple[str, str, list[dict[str, object]]]:
    html = await _read_text(file_source, encoding=encoding)
    return await asyncio.to_thread(_parse_html, html)


async def _read_text(
    file_source: str | Path | bytes | BinaryIO,
    *,
    encoding: str,
) -> str:
    if isinstance(file_source, bytes):
        content = file_source
    elif isinstance(file_source, (str, Path)):
        content = await asyncio.to_thread(Path(file_source).read_bytes)
    else:
        content = await asyncio.to_thread(file_source.read)
        if not isinstance(content, bytes):
            raise TypeError("file_source.read() 必须返回 bytes。")
    return content.decode(encoding)


def _parse_html(html: str) -> tuple[str, str, list[dict[str, object]]]:
    from bs4 import BeautifulSoup
    from markdownify import markdownify

    soup = BeautifulSoup(html, "html.parser")
    for node in soup.find_all(["script", "style", "noscript", "template"]):
        node.decompose()
    root = soup.body or soup
    cleaned_html = str(root)
    markdown = markdownify(cleaned_html, heading_style="ATX").strip()
    elements = [{"type": node.name, "text": node.get_text(" ", strip=True)} for node in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "a", "table"])]
    return markdown, cleaned_html, elements
