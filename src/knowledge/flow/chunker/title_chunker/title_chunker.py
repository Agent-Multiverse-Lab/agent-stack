from __future__ import annotations

from typing import Literal

from ...types import DocumentChunk, ParsedDocument
from ..common import DEFAULT_CHUNK_TOKEN_SIZE, resolve_outline_levels
from .group_chunker import GroupTitleChunker
from .hierarchy_chunker import HierarchyTitleChunker

TitleMethod = Literal["group", "hierarchy"]


class TitleChunker:
    """显式选择一种标题分块策略。"""

    def __init__(
        self,
        *,
        method: TitleMethod = "group",
        target_level: int = 3,
        chunk_token_size: int = DEFAULT_CHUNK_TOKEN_SIZE,
    ) -> None:
        implementations = {
            "group": GroupTitleChunker,
            "hierarchy": HierarchyTitleChunker,
        }
        implementation = implementations.get(method)
        if implementation is None:
            raise ValueError(f"不支持的标题分块方式：{method!r}，应为 'group' 或 'hierarchy'")
        self.method = method
        self._implementation = implementation(
            target_level=target_level,
            chunk_token_size=chunk_token_size,
        )

    def chunk(self, document: ParsedDocument) -> list[DocumentChunk]:
        return self._implementation.chunk(resolve_outline_levels(document))


__all__ = ["TitleChunker", "TitleMethod"]
