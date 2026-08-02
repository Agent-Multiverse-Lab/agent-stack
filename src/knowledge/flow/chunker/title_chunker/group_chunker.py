from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from src.knowledge.flow.chunker.common import (
    normalize_text,
)
from src.knowledge.flow.chunker.title_chunker.common import (
    BODY_LEVEL,
    BaseTitleChunker,
    ResolvedLevels,
)
from src.knowledge.flow.chunker.token_chunker import TokenChunker
from src.knowledge.flow.types import DocumentBlock, DocumentChunk, ParsedDocument

_ATOMIC_KINDS = {"table", "image"}


class GroupTitleChunker(BaseTitleChunker):
    """尽量合并同一目标标题段落内的内容，绝不跨段落合并。"""

    def resolve_levels(
        self,
        document: ParsedDocument,
        line_records: Sequence[DocumentBlock],
    ) -> ResolvedLevels:
        """复用 BaseTitleChunker 的 outline 与正则层级解析。"""
        return self.resolve_title_levels(
            document,
            line_records,
        )

    def build_chunks(
        self,
        document: ParsedDocument,
        line_records: Sequence[DocumentBlock],
        resolved: ResolvedLevels,
    ) -> list[DocumentChunk]:
        """按目标标题层级建立 section 并在 section 内固定切分。"""
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
            chunks.extend(
                TokenChunker(
                    chunk_token_size=self.chunk_token_size,
                ).chunk(section_document)
            )
            buffered_blocks.clear()

        for block, level in zip(line_records, resolved.levels):
            if level != BODY_LEVEL:
                title = normalize_text(block.text)
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


def _push_heading(
    stack: list[tuple[int, str]],
    level: int,
    title: str,
) -> None:
    while stack and stack[-1][0] >= level:
        stack.pop()
    stack.append((level, title))


__all__ = ["GroupTitleChunker"]
