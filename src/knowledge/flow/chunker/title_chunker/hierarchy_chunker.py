from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from src.knowledge.flow.chunker.common import (
    count_tokens,
    join_texts,
    normalize_text,
    split_blocks_fixed,
)
from src.knowledge.flow.chunker.title_chunker.common import (
    BODY_LEVEL,
    BaseTitleChunker,
    ResolvedLevels,
)
from src.knowledge.flow.types import DocumentBlock, DocumentChunk, ParsedDocument

_ATOMIC_KINDS = {"table", "image"}


@dataclass(slots=True)
class _HeadingNode:
    level: int
    title: DocumentBlock | None = None
    items: list[DocumentBlock | _HeadingNode] = field(default_factory=list)

    def build_tree(
        self,
        line_records: Sequence[DocumentBlock],
        levels: Sequence[int],
        target_level: int,
    ) -> _HeadingNode:
        """使用标题层级栈构建保持原始块顺序的结构树。"""
        stack = [self]
        for block, level in zip(line_records, levels):
            if level == BODY_LEVEL:
                stack[-1].items.append(block)
                continue

            title = normalize_text(block.text)
            if not title or level > target_level:
                stack[-1].items.append(block)
                continue

            while len(stack) > 1 and stack[-1].level >= level:
                stack.pop()
            node = _HeadingNode(level=level, title=block)
            stack[-1].items.append(node)
            stack.append(node)
        return self


class HierarchyTitleChunker(BaseTitleChunker):
    """构建标题树，并在正文和 metadata 中保留每个节点的完整路径。"""

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
        """构造标题结构树并沿节点路径生成分块。"""
        root = _HeadingNode(level=0).build_tree(
            line_records,
            resolved.levels,
            self.target_level,
        )
        chunks: list[DocumentChunk] = []
        self._collect_node(document, root, [], chunks)
        return chunks

    def _collect_node(
        self,
        document: ParsedDocument,
        node: _HeadingNode,
        parent_path: list[str],
        chunks: list[DocumentChunk],
    ) -> None:
        path = list(parent_path)
        if node.title is not None:
            title = normalize_text(node.title.text)
            if title:
                path.append(title)

        start_count = len(chunks)
        buffered_blocks: list[DocumentBlock] = []

        def flush_text() -> None:
            if not buffered_blocks:
                return
            chunks.extend(
                _path_chunks(
                    buffered_blocks,
                    document,
                    path=path,
                    heading_level=node.level,
                    chunk_token_size=self.chunk_token_size,
                )
            )
            buffered_blocks.clear()

        for item in node.items:
            if isinstance(item, _HeadingNode):
                flush_text()
                self._collect_node(document, item, path, chunks)
                continue

            if item.kind not in _ATOMIC_KINDS:
                buffered_blocks.append(item)
                continue

            flush_text()
            metadata = _path_metadata(
                document,
                path=path,
                heading_level=node.level,
            )
            metadata.update(item.metadata)
            metadata["heading_path"] = list(path)
            if node.level:
                metadata["heading_level"] = node.level
            chunks.append(
                DocumentChunk(
                    text=_with_path(path, normalize_text(item.text)),
                    kind=item.kind,
                    metadata=metadata,
                )
            )

        flush_text()
        if node.title is not None and len(chunks) == start_count:
            metadata = _path_metadata(
                document,
                path=path,
                heading_level=node.level,
            )
            chunks.append(
                DocumentChunk(
                    text=join_texts(path),
                    kind="text",
                    metadata=metadata,
                )
            )


def _path_chunks(
    blocks: list[DocumentBlock],
    document: ParsedDocument,
    *,
    path: list[str],
    heading_level: int,
    chunk_token_size: int,
) -> list[DocumentChunk]:
    prefix = join_texts(path)
    if prefix:
        prefix_token_count = count_tokens(f"{prefix}\n")
        body_chunk_size = max(1, chunk_token_size - prefix_token_count)
    else:
        body_chunk_size = chunk_token_size

    chunks: list[DocumentChunk] = []
    for part in split_blocks_fixed(blocks, body_chunk_size):
        if not part.text:
            continue
        chunks.append(
            DocumentChunk(
                text=_with_path(path, part.text),
                kind="text",
                metadata=_content_metadata(
                    document,
                    part.blocks,
                    path=path,
                    heading_level=heading_level,
                ),
            )
        )
    return chunks


def _with_path(path: list[str], body: str) -> str:
    return join_texts([join_texts(path), body])


def _content_metadata(
    document: ParsedDocument,
    blocks: tuple[DocumentBlock, ...],
    *,
    path: list[str],
    heading_level: int,
) -> dict[str, Any]:
    metadata = _path_metadata(
        document,
        path=path,
        heading_level=heading_level,
    )
    block_metadata = [dict(block.metadata) for block in blocks if block.metadata]
    if block_metadata:
        metadata["block_metadata"] = block_metadata
    return metadata


def _path_metadata(
    document: ParsedDocument,
    *,
    path: list[str],
    heading_level: int,
) -> dict[str, Any]:
    metadata = dict(document.metadata)
    metadata["heading_path"] = list(path)
    if heading_level:
        metadata["heading_level"] = heading_level
    return metadata


__all__ = ["HierarchyTitleChunker"]
