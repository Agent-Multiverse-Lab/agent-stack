from __future__ import annotations

import re
import sys
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal

from src.knowledge.flow.chunker.common import (
    DEFAULT_CHUNK_TOKEN_SIZE,
    build_pdf_json_blocks,
    normalize_text,
    validate_chunk_token_size,
)
from src.knowledge.flow.types import DocumentBlock, DocumentChunk, ParsedDocument
from src.utils import logger

BODY_LEVEL = sys.maxsize - 1
_OUTLINE_SIMILARITY_THRESHOLD = 0.8

_TITLE_LEVEL_GROUPS = (
    (
        r"^#[^#]",
        r"^##[^#]",
        r"^###[^#]",
        r"^####[^#]",
    ),
    (
        r"第[零一二三四五六七八九十百0-9]+(分?编|部分)",
        r"第[零一二三四五六七八九十百0-9]+章",
        r"第[零一二三四五六七八九十百0-9]+节",
        r"第[零一二三四五六七八九十百0-9]+条",
        r"[\(（][零一二三四五六七八九十百]+[\)）]",
    ),
    (
        r"第[0-9]+章",
        r"第[0-9]+节",
        r"[0-9]{1,2}[\. 、]",
        r"[0-9]{1,2}\.[0-9]{1,2}($|[^a-zA-Z/%~.-])",
        r"[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{1,2}",
    ),
    (
        r"第[零一二三四五六七八九十百0-9]+章",
        r"第[零一二三四五六七八九十百0-9]+节",
        r"[零一二三四五六七八九十百]+[ 、]",
        r"[\(（][零一二三四五六七八九十百]+[\)）]",
        r"[\(（][0-9]{0,2}[\)）]",
    ),
    (
        r"PART (ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN)",
        r"Chapter (I+V?|VI*|XI|IX|X)",
        r"Section [0-9]+",
        r"Article [0-9]+",
    ),
)


@dataclass(slots=True)
class ResolvedLevels:
    """保存与文档块对齐的标题层级解析结果。"""

    levels: list[int]
    most_level: int | None
    source: Literal["outline", "frequency"]


class BaseTitleChunker(ABC):
    """统一标题层级解析流程，子类只决定如何消费层级结构。"""

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

    def invoke(self, document: ParsedDocument) -> list[DocumentChunk]:
        """按统一流程解析层级并执行具体标题分块策略。"""
        resolved_document, line_records = self.extract_line_records(document)
        resolved = self.resolve_levels(resolved_document, line_records)
        logger.info(
            "%s 标题层级解析完成：file_name=%s source=%s titles=%s",
            type(self).__name__,
            resolved_document.name,
            resolved.source,
            sum(level < BODY_LEVEL for level in resolved.levels),
        )
        return self.build_chunks(resolved_document, line_records, resolved)

    @staticmethod
    def extract_line_records(
        document: ParsedDocument,
    ) -> tuple[ParsedDocument, list[DocumentBlock]]:
        """将 PDF JSON 或普通文档块归一化为有序块记录。"""
        pdf_json_blocks = build_pdf_json_blocks(document)
        if pdf_json_blocks:
            document = replace(document, blocks=pdf_json_blocks)
        return document, document.blocks

    def resolve_title_levels(
        self,
        document: ParsedDocument,
        line_records: Sequence[DocumentBlock],
    ) -> ResolvedLevels:
        """优先匹配 PDF outline，未有效命中时回退到正则频率。"""
        return self.resolve_outline_levels(
            document,
            line_records,
        ) or self.resolve_frequency_levels(line_records)

    @staticmethod
    def resolve_outline_levels(
        document: ParsedDocument,
        line_records: Sequence[DocumentBlock],
    ) -> ResolvedLevels | None:
        """使用 RAGFlow 的 bigram 思路将 PDF outline 映射到块层级。"""
        if not line_records or not document.outlines:
            return None
        if len(document.outlines) / len(line_records) <= 0.03:
            return None

        candidates = [
            (index, _outline_text(title), max(depth + 1, 1))
            for index, (title, depth, _) in enumerate(document.outlines)
            if _outline_text(title)
        ]
        levels = [BODY_LEVEL] * len(line_records)
        matched_candidates: set[int] = set()

        for block_index, block in enumerate(line_records):
            if block.kind in {"table", "image"}:
                continue

            match = _match_outline(
                block.text,
                candidates,
                matched_candidates,
            )
            if match is None:
                continue
            candidate_index, level = match
            matched_candidates.add(candidate_index)
            levels[block_index] = level

        if not matched_candidates:
            return None
        return ResolvedLevels(
            levels=levels,
            most_level=_most_common_title_level(levels),
            source="outline",
        )

    @staticmethod
    def resolve_frequency_levels(
        line_records: Sequence[DocumentBlock],
    ) -> ResolvedLevels:
        """选择命中次数最多的 RAGFlow 标题正则族并解析层级。"""
        level_group = _select_level_group(
            [block.text for block in line_records],
        )
        fallback_level = len(level_group) + 1
        levels: list[int] = []

        for block in line_records:
            if block.kind in {"table", "image"}:
                levels.append(BODY_LEVEL)
                continue
            if block.kind == "title" and block.heading_level is not None:
                levels.append(block.heading_level)
                continue

            level = _match_regex_level(block.text, level_group)
            if level is not None:
                levels.append(level)
                continue
            levels.append(_match_layout_level(block, fallback_level))

        return ResolvedLevels(
            levels=levels,
            most_level=_most_common_title_level(levels),
            source="frequency",
        )

    @abstractmethod
    def resolve_levels(
        self,
        document: ParsedDocument,
        line_records: Sequence[DocumentBlock],
    ) -> ResolvedLevels:
        """解析当前策略使用的标题层级。"""
        raise NotImplementedError

    @abstractmethod
    def build_chunks(
        self,
        document: ParsedDocument,
        line_records: Sequence[DocumentBlock],
        resolved: ResolvedLevels,
    ) -> list[DocumentChunk]:
        """根据已解析层级构造最终分块。"""
        raise NotImplementedError


def _select_level_group(lines: Sequence[str]) -> tuple[str, ...]:
    hits = [0] * len(_TITLE_LEVEL_GROUPS)
    for group_index, group in enumerate(_TITLE_LEVEL_GROUPS):
        for line in lines:
            stripped = normalize_text(line)
            if any(re.match(pattern, stripped) for pattern in group):
                hits[group_index] += 1

    maximum = 0
    selected = -1
    for group_index, hit in enumerate(hits):
        if hit <= maximum:
            continue
        maximum = hit
        selected = group_index
    return _TITLE_LEVEL_GROUPS[selected] if selected >= 0 else ()


def _match_regex_level(
    text: str,
    level_group: Sequence[str],
) -> int | None:
    stripped = normalize_text(text)
    for level, pattern in enumerate(level_group, start=1):
        if re.match(pattern, stripped):
            return level
    return None


def _match_layout_level(
    block: DocumentBlock,
    fallback_level: int,
) -> int:
    if block.kind == "title":
        return block.heading_level or fallback_level

    layout = " ".join(
        str(block.metadata.get(key) or "")
        for key in ("layout_type", "layout")
    )
    if re.search(r"(section|title|head)", layout, re.IGNORECASE):
        return fallback_level
    return BODY_LEVEL


def _match_outline(
    text: str,
    candidates: Sequence[tuple[int, str, int]],
    matched_candidates: set[int],
) -> tuple[int, int] | None:
    normalized_text = _outline_text(text)
    best_match: tuple[int, int] | None = None
    best_score = _OUTLINE_SIMILARITY_THRESHOLD

    for index, title, level in candidates:
        if index in matched_candidates:
            continue
        score = _bigram_similarity(title, normalized_text)
        if score <= best_score:
            continue
        best_match = (index, level)
        best_score = score
    return best_match


def _outline_text(text: str) -> str:
    return re.sub(r"\s+", "", normalize_text(text)).casefold()


def _bigram_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    if len(left) < 2 or len(right) < 2:
        return 0.0

    left_pairs = {left[index : index + 2] for index in range(len(left) - 1)}
    right_pairs = {right[index : index + 2] for index in range(len(right) - 1)}
    return len(left_pairs & right_pairs) / max(
        len(left_pairs),
        len(right_pairs),
        1,
    )


def _most_common_title_level(levels: Sequence[int]) -> int | None:
    for level, _ in Counter(levels).most_common():
        if level < BODY_LEVEL:
            return level
    return None


__all__ = [
    "BODY_LEVEL",
    "BaseTitleChunker",
    "ResolvedLevels",
]
