from __future__ import annotations

from pathlib import Path
from typing import BinaryIO, Literal

from .chunker import TitleChunker, TokenChunker
from .parser import Parser
from .parser.parser import (
    _SUFFIX_HANDLERS,
    _resolve_file_name,
)
from .types import DocumentChunk, ParsedDocument

ChunkerName = Literal["token", "title"]
TitleChunkerMethod = Literal["group", "hierarchy"]


class DocumentFlow:
    def __init__(self, parser: Parser | None = None) -> None:
        self._parser = parser or Parser()

    async def parse_document(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
    ) -> ParsedDocument:
        name, suffix = _resolve_file_name(file_name)
        handler_name = _SUFFIX_HANDLERS.get(suffix)
        if handler_name is None:
            supported = ", ".join(sorted(_SUFFIX_HANDLERS))
            raise ValueError(f"不支持的文件后缀：{suffix!r}。支持的后缀：{supported}。")

        source = "filename" if isinstance(file_source, (str, Path)) else "byte_stream"

        handler = getattr(self._parser, handler_name)
        parsed = await handler(file_source, file_name=name)
        return await self._parser._document(
            file_source,
            name=name,
            source=source,
            parsed=parsed,
        )

    async def run(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
        chunker: ChunkerName = "title",
        title_method: TitleChunkerMethod = "hierarchy",
        target_level: int = 3,
        chunk_token_size: int = 512,
    ) -> list[DocumentChunk]:
        document = await self.parse_document(file_source, file_name=file_name)

        if chunker == "token":
            return TokenChunker(chunk_token_size=chunk_token_size).chunk(document)
        if chunker == "title":
            return TitleChunker(
                method=title_method,
                target_level=target_level,
                chunk_token_size=chunk_token_size,
            ).chunk(document)
        raise ValueError(f"不支持的 chunker：{chunker!r}")


__all__ = [
    "ChunkerName",
    "DocumentFlow",
    "TitleChunkerMethod",
]
