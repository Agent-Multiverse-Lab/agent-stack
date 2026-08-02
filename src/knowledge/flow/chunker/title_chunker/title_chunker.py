from __future__ import annotations

from typing import Literal

from src.knowledge.flow.chunker.common import DEFAULT_CHUNK_TOKEN_SIZE
from src.knowledge.flow.chunker.title_chunker.group_chunker import (
    GroupTitleChunker,
)
from src.knowledge.flow.chunker.title_chunker.hierarchy_chunker import (
    HierarchyTitleChunker,
)
from src.knowledge.flow.types import DocumentChunk, ParsedDocument

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
        if method not in {"group", "hierarchy"}:
            raise ValueError(f"不支持的标题分块方式：{method!r}，应为 'group' 或 'hierarchy'")
        self.method = method
        self.target_level = target_level
        self.chunk_token_size = chunk_token_size

    def chunk(self, document: ParsedDocument) -> list[DocumentChunk]:
        """保留 Pipeline 使用的同步 Chunker 入口。"""
        return self._invoke(document)

    def _invoke(self, document: ParsedDocument) -> list[DocumentChunk]:
        """根据 method 调度具体标题分块器。"""
        parameters = {
            "target_level": self.target_level,
            "chunk_token_size": self.chunk_token_size,
        }
        if self.method == "hierarchy":
            return HierarchyTitleChunker(**parameters).invoke(document)
        if self.method == "group":
            return GroupTitleChunker(**parameters).invoke(document)
        raise ValueError(f"不支持的标题分块方式：{self.method!r}")


__all__ = ["TitleChunker", "TitleMethod"]
