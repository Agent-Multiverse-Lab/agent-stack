from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...types import DocumentBlock, DocumentChunk, ParsedDocument
from ..common import (
    BODY_LEVEL,
    DEFAULT_CHUNK_TOKEN_SIZE,
    count_tokens,
    join_texts,
    normalize_text,
    split_blocks_fixed,
    validate_chunk_token_size,
)

_ATOMIC_KINDS = {"table", "image"}


@dataclass(slots=True)
class _HeadingNode:
    level: int
    title: DocumentBlock | None = None
    items: list[DocumentBlock | _HeadingNode] = field(default_factory=list)


class HierarchyTitleChunker:
    """构建标题树，并在正文和 metadata 中保留每个节点的完整路径。"""

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

    def chunk(
        self,
        document: ParsedDocument,
        levels: list[int],
    ) -> list[DocumentChunk]:
        root = self._build_tree(document, levels)
        chunks: list[DocumentChunk] = []
        self._collect_node(document, root, [], chunks)
        return chunks

    def _build_tree(
        self,
        document: ParsedDocument,
        levels: list[int],
    ) -> _HeadingNode:
        root = _HeadingNode(level=0)
        stack = [root]

        for block_index, block in enumerate(document.blocks):
            level = levels[block_index]
            if level == BODY_LEVEL:
                stack[-1].items.append(block)
                continue

            title = normalize_text(block.text)
            if not title or level > self.target_level:
                stack[-1].items.append(block)
                continue

            while len(stack) > 1 and stack[-1].level >= level:
                stack.pop()
            node = _HeadingNode(level=level, title=block)
            stack[-1].items.append(node)
            stack.append(node)

        return root

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
