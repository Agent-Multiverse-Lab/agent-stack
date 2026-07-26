from __future__ import annotations

from typing import Any

from ..types import DocumentBlock, DocumentChunk, ParsedDocument
from .common import (
    DEFAULT_CHUNK_TOKEN_SIZE,
    normalize_text,
    split_blocks_fixed,
    validate_chunk_token_size,
)

_ATOMIC_KINDS = {"table", "image"}


class TokenChunker:
    """按固定 token 步长切分连续的正文块和标题块。"""

    def __init__(
        self,
        *,
        chunk_token_size: int = DEFAULT_CHUNK_TOKEN_SIZE,
    ) -> None:
        validate_chunk_token_size(chunk_token_size)
        self.chunk_token_size = chunk_token_size

    def chunk(self, document: ParsedDocument) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        text_blocks: list[DocumentBlock] = []

        def flush_text_blocks() -> None:
            if not text_blocks:
                return
            chunks.extend(
                DocumentChunk(
                    text=part.text,
                    kind="text",
                    metadata=_text_metadata(document, part.blocks),
                )
                for part in split_blocks_fixed(
                    text_blocks,
                    self.chunk_token_size,
                )
                if part.text
            )
            text_blocks.clear()

        for block in document.blocks:
            if block.kind not in _ATOMIC_KINDS:
                text_blocks.append(block)
                continue

            flush_text_blocks()
            text = normalize_text(block.text)
            chunks.append(
                DocumentChunk(
                    text=text,
                    kind=block.kind,
                    metadata=_atomic_metadata(document, block),
                )
            )

        flush_text_blocks()
        return chunks


def _text_metadata(
    document: ParsedDocument,
    blocks: tuple[DocumentBlock, ...],
) -> dict[str, Any]:
    metadata = dict(document.metadata)
    headings = [
        {
            "text": normalize_text(block.text),
            "heading_level": block.heading_level,
            "metadata": dict(block.metadata),
        }
        for block in blocks
        if block.kind == "title" and normalize_text(block.text)
    ]
    if headings:
        metadata["headings"] = headings

    block_metadata = [dict(block.metadata) for block in blocks if block.metadata]
    if block_metadata:
        metadata["block_metadata"] = block_metadata
    return metadata


def _atomic_metadata(
    document: ParsedDocument,
    block: DocumentBlock,
) -> dict[str, Any]:
    return {**document.metadata, **block.metadata}


__all__ = ["TokenChunker"]
