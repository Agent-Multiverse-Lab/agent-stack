from __future__ import annotations

from pathlib import Path
from typing import BinaryIO, Literal

from src.utils import logger

from .chunker import TitleChunker, TokenChunker
from .parser import Parser
from .types import DocumentChunk, ParsedDocument

ChunkerName = Literal["token", "title"]
TitleChunkerMethod = Literal["group", "hierarchy"]


class Pipeline:
    def __init__(
        self,
        parser: Parser | None = None,
    ) -> None:
        self._parser = parser or Parser()

    async def parse_document(
        self,
        file_source: str | Path | bytes | BinaryIO,
        *,
        file_name: str,
    ) -> ParsedDocument:
        logger.info("Pipeline 开始解析文档：file_name=%s", file_name)
        document = await self._parser.parse(
            file_source,
            file_name=file_name,
        )
        logger.info(
            "Pipeline 文档解析完成：file_name=%s suffix=%s blocks=%s",
            document.name,
            document.suffix,
            len(document.blocks),
        )
        return document

    def chunk_document(
        self,
        document: ParsedDocument,
        *,
        chunker: ChunkerName = "title",
        title_method: TitleChunkerMethod = "hierarchy",
        target_level: int = 3,
        chunk_token_size: int = 512,
    ) -> list[DocumentChunk]:
        """对已确认的解析结果执行显式分块。"""
        logger.info(
            "Pipeline 开始分块：file_name=%s chunker=%s chunk_token_size=%s",
            document.name,
            chunker,
            chunk_token_size,
        )
        try:
            if chunker == "token":
                chunks = TokenChunker(
                    chunk_token_size=chunk_token_size
                ).chunk(document)
            elif chunker == "title":
                chunks = TitleChunker(
                    method=title_method,
                    target_level=target_level,
                    chunk_token_size=chunk_token_size,
                ).chunk(document)
            else:
                raise ValueError(f"不支持的 Chunker：{chunker}")
        except Exception:
            logger.exception(
                "Pipeline 分块失败：file_name=%s chunker=%s",
                document.name,
                chunker,
            )
            raise

        logger.info(
            "Pipeline 分块完成：file_name=%s chunks=%s",
            document.name,
            len(chunks),
        )
        return chunks


__all__ = [
    "ChunkerName",
    "Pipeline",
    "TitleChunkerMethod",
]
