from __future__ import annotations

import asyncio
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlparse

from src.configs.config import config


class DocParser:
    name = "doc"

    async def parse(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        as_json: bool = False,
    ) -> str | dict[str, object]:
        content = await _read_file_source(file_source)
        response_text, response_type = await _request_tika(content)
        html, text = await asyncio.to_thread(
            _clean_tika_response,
            response_text,
            response_type,
        )
        if content and not text:
            raise RuntimeError("Tika returned no content.")
        if as_json:
            return {
                "html": html,
                "text": text,
                "content_type": response_type,
            }
        return await asyncio.to_thread(_tika_markdown, html, text)


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


async def _request_tika(content: bytes) -> tuple[str, str]:
    import httpx

    base_url = config.tika_server_url.strip()
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError("TIKA_SERVER_URL is not configured or invalid.")
    endpoint = base_url.rstrip("/")
    if not endpoint.endswith("/tika"):
        endpoint += "/tika"

    async with httpx.AsyncClient(timeout=float(config.document_parser_api_timeout_seconds)) as client:
        response = await client.put(
            endpoint,
            content=content,
            headers={
                "Accept": "text/html",
                "Content-Type": "application/msword",
            },
        )
    response.raise_for_status()
    return response.text, response.headers.get("content-type", "")


def _clean_tika_response(raw: str, content_type: str) -> tuple[str, str]:
    if "html" not in content_type.lower() and "<html" not in raw.lower():
        text = raw.strip()
        return "", text

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(raw, "html.parser")
    for node in soup.find_all(["script", "style", "noscript"]):
        node.decompose()
    root = soup.body or soup
    return str(root), root.get_text(
        "\n",
        strip=True,
    )


def _tika_markdown(html: str, text: str) -> str:
    if not html:
        return text

    from markdownify import markdownify

    return markdownify(html, heading_style="ATX").strip()
