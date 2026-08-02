from __future__ import annotations

import asyncio
from pathlib import Path
from typing import BinaryIO


class TextParser:
    name = "txt"

    async def parse(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        encoding: str = "utf-8-sig",
        as_json: bool = False,
    ) -> str | dict[str, object]:
        text = await _read_text(file_source, encoding=encoding)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if not as_json:
            return text
        return {
            "text": text,
            "paragraphs": [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()],
        }


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
