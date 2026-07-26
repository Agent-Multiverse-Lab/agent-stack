from __future__ import annotations

from typing import Any

from ...types import DocumentBlock, DocumentChunk, ParsedDocument
from ..common import (
    DEFAULT_CHUNK_TOKEN_SIZE,
    normalize_text,
    validate_chunk_token_size,
)
from ..token_chunker import TokenChunker

_ATOMIC_KINDS = {"table", "image"}


class GroupTitleChunker:
    """尽量合并同一目标标题段落内的内容，绝不跨段落合并。"""

    def __init__(
        self,
        *,
        target_level: int = 3,
        chunk_token_size: int = DEFAULT_CHUNK_TOKEN_SIZE,
    ) -> None:
        if target_level <= 0:
            raise ValueError("target_level 必须大于 0")
        validate_chunk_token_size(chunk_token_size)
        self.target_level = target_level
        self.chunk_token_size = chunk_token_size
        self._token_chunker = TokenChunker(
            chunk_token_size=chunk_token_size,
        )

    def chunk(self, document: ParsedDocument) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        buffered_blocks: list[DocumentBlock] = []
        heading_stack: list[tuple[int, str]] = []
        section_path: list[str] = []
        section_level: int | None = None

        def section_metadata() -> dict[str, Any]:
            metadata = dict(document.metadata)
            metadata["heading_path"] = list(section_path)
            if section_level is not None:
                metadata["heading_level"] = section_level
            return metadata

        def flush_text() -> None:
            if not buffered_blocks:
                return
            section_document = ParsedDocument(
                name=document.name,
                suffix=document.suffix,
                blocks=list(buffered_blocks),
                metadata=section_metadata(),
            )
            chunks.extend(self._token_chunker.chunk(section_document))
            buffered_blocks.clear()

        for block in document.blocks:
            if block.kind == "title":
                title = normalize_text(block.text)
                level = _heading_level(block)
                if title and level <= self.target_level:
                    flush_text()
                    _push_heading(heading_stack, level, title)
                    section_path = [heading for _, heading in heading_stack]
                    section_level = level
                elif title:
                    _push_heading(heading_stack, level, title)
                buffered_blocks.append(block)
                continue

            if block.kind not in _ATOMIC_KINDS:
                buffered_blocks.append(block)
                continue

            flush_text()
            metadata = {
                **section_metadata(),
                **block.metadata,
            }
            metadata["heading_path"] = list(section_path)
            if section_level is not None:
                metadata["heading_level"] = section_level
            chunks.append(
                DocumentChunk(
                    text=normalize_text(block.text),
                    kind=block.kind,
                    metadata=metadata,
                )
            )

        flush_text()
        return chunks


def _heading_level(block: DocumentBlock) -> int:
    return block.heading_level if block.heading_level is not None else 1


def _push_heading(
    stack: list[tuple[int, str]],
    level: int,
    title: str,
) -> None:
    while stack and stack[-1][0] >= level:
        stack.pop()
    stack.append((level, title))


__all__ = ["GroupTitleChunker"]
