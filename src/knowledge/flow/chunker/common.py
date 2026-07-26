from __future__ import annotations

import hashlib
import html
import os
import re
import tempfile
from bisect import bisect_right
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

import tiktoken

from src.knowledge.file_parser.utils.parser_pdf_outline import extract_pdf_outline

from ..types import DocumentBlock, ParsedDocument

DEFAULT_CHUNK_TOKEN_SIZE = 512

_CL100K_BASE_URL = "https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken"
_CL100K_BASE_HASH = "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"
_POSITION_TAG_RE = re.compile(r"@@\d+(?:\t[-+]?\d+(?:\.\d+)?){4}##")
_OUTLINE_SIMILARITY_THRESHOLD = 0.8


@dataclass(slots=True)
class SourcedTextPart:
    """固定切分后的一段文本，以及它实际覆盖的来源块。"""

    text: str
    blocks: tuple[DocumentBlock, ...]


def validate_chunk_token_size(chunk_token_size: int) -> None:
    if chunk_token_size <= 0:
        raise ValueError("chunk_token_size 必须大于 0")


@lru_cache(maxsize=1)
def _token_encoder() -> tiktoken.Encoding | None:
    """仅在本地存在校验通过的缓存文件时加载 cl100k。"""
    cache_dir = os.getenv("TIKTOKEN_CACHE_DIR") or os.getenv("DATA_GYM_CACHE_DIR") or str(Path(tempfile.gettempdir()) / "data-gym-cache")
    cache_key = hashlib.sha1(_CL100K_BASE_URL.encode()).hexdigest()
    cache_path = Path(cache_dir) / cache_key
    if not cache_path.is_file():
        return None

    try:
        if hashlib.sha256(cache_path.read_bytes()).hexdigest() != _CL100K_BASE_HASH:
            return None
        return tiktoken.get_encoding("cl100k_base")
    except (OSError, ValueError):
        return None


def count_tokens(text: str) -> int:
    value = text or ""
    encoder = _token_encoder()
    if encoder is not None:
        return len(encoder.encode(value, disallowed_special=()))
    return len(_offline_tokens(value))


def split_text_fixed(text: str, chunk_token_size: int) -> list[str]:
    """按固定 token 数连续切分文本，不产生重叠。"""
    validate_chunk_token_size(chunk_token_size)
    if not text:
        return []

    encoder = _token_encoder()
    if encoder is not None:
        token_ids = encoder.encode(text, disallowed_special=())
        return _split_encoded_tokens(encoder, token_ids, chunk_token_size)

    tokens = _offline_tokens(text)
    return ["".join(tokens[index : index + chunk_token_size]) for index in range(0, len(tokens), chunk_token_size)]


def split_blocks_fixed(
    blocks: Sequence[DocumentBlock],
    chunk_token_size: int,
) -> list[SourcedTextPart]:
    """拼接并固定切分来源块，同时精确记录每一段覆盖了哪些块。"""
    normalized_blocks: list[tuple[DocumentBlock, str]] = []
    for block in blocks:
        text = normalize_text(block.text)
        if text:
            normalized_blocks.append((block, text))

    if not normalized_blocks:
        return []

    spans: list[tuple[int, int, DocumentBlock]] = []
    texts: list[str] = []
    position = 0
    for block, text in normalized_blocks:
        if texts:
            position += 1
        start = position
        position += len(text)
        spans.append((start, position, block))
        texts.append(text)

    parts: list[SourcedTextPart] = []
    part_start = 0
    span_index = 0
    for text in split_text_fixed(join_texts(texts), chunk_token_size):
        part_end = part_start + len(text)
        while span_index < len(spans) and spans[span_index][1] <= part_start:
            span_index += 1

        covered_blocks: list[DocumentBlock] = []
        current_span = span_index
        while current_span < len(spans):
            block_start, block_end, block = spans[current_span]
            if block_start >= part_end:
                break
            if block_end > part_start:
                covered_blocks.append(block)
            current_span += 1

        parts.append(
            SourcedTextPart(
                text=text,
                blocks=tuple(covered_blocks),
            )
        )
        part_start = part_end
    return parts


def normalize_text(text: str) -> str:
    normalized = html.unescape(text or "")
    normalized = _POSITION_TAG_RE.sub("", normalized)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n").replace("\u3000", " ")
    lines = [re.sub(r" +", " ", line).strip() for line in normalized.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def resolve_outline_levels(document: ParsedDocument) -> ParsedDocument:
    """用 PDF 原始大纲为解析后的 JSON 内容补充标题层级。"""
    if document.suffix.lower() != ".pdf":
        return document
    if document.json_result is None:
        return document

    outlines = document.outlines
    if not outlines and document.file_source is not None:
        outlines = extract_pdf_outline(document.file_source)
    if not outlines:
        return document

    line_blocks = _pdf_json_line_blocks(document.json_result)
    if not line_blocks:
        return document

    candidates: list[tuple[int, str, int]] = []
    for index, (title, depth, _) in enumerate(outlines):
        normalized_title = _outline_match_text(title)
        if not normalized_title:
            continue
        candidate = (index, normalized_title, max(depth + 1, 1))
        candidates.append(candidate)

    resolved_blocks: list[DocumentBlock] = []
    matched_candidates: set[int] = set()
    matched_count = 0
    for block in line_blocks:
        level = _match_outline_level(
            block.text,
            candidates,
            matched_candidates,
        )
        if level is None:
            resolved_blocks.append(block)
            continue

        matched_count += 1
        metadata = dict(block.metadata)
        metadata.update(
            {
                "element_type": "heading",
                "outline": True,
            }
        )
        resolved_blocks.append(
            DocumentBlock(
                text=block.text,
                kind="title",
                heading_level=level,
                metadata=metadata,
            )
        )

    if matched_count == 0:
        return document
    return replace(document, blocks=resolved_blocks)


def _pdf_json_line_blocks(
    json_result: Sequence[Mapping[str, object]],
) -> list[DocumentBlock]:
    blocks: list[DocumentBlock] = []
    for item in json_result:
        text = normalize_text(str(item.get("text") or ""))
        if not text:
            continue
        blocks.append(
            DocumentBlock(
                text=text,
                metadata={
                    "element_type": "paragraph",
                },
            )
        )
    return blocks


def _match_outline_level(
    text: str,
    candidates: Sequence[tuple[int, str, int]],
    matched_candidates: set[int],
) -> int | None:
    normalized_text = _outline_match_text(text)
    if not normalized_text:
        return None

    for index, title, level in candidates:
        if index not in matched_candidates and normalized_text == title:
            matched_candidates.add(index)
            return level

    for index, title, level in candidates:
        if index in matched_candidates:
            continue
        if _outline_prefix_match(normalized_text, title):
            matched_candidates.add(index)
            return level

    best_match: tuple[int, int] | None = None
    best_score = _OUTLINE_SIMILARITY_THRESHOLD
    for index, title, level in candidates:
        if index in matched_candidates:
            continue
        score = _outline_similarity(normalized_text, title)
        if score < best_score:
            continue
        best_match = (index, level)
        best_score = score

    if best_match is None:
        return None
    matched_candidates.add(best_match[0])
    return best_match[1]


def _outline_match_text(text: str) -> str:
    return re.sub(r"\s+", "", normalize_text(text)).casefold()


def _outline_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    if len(left) < 2 or len(right) < 2:
        return 0.0

    left_pairs = {left[index : index + 2] for index in range(len(left) - 1)}
    right_pairs = {right[index : index + 2] for index in range(len(right) - 1)}
    return len(left_pairs & right_pairs) / max(len(left_pairs), len(right_pairs), 1)


def _outline_prefix_match(left: str, right: str) -> bool:
    shorter, longer = sorted((left, right), key=len)
    if len(shorter) < 6 or not longer.startswith(shorter):
        return False
    return len(shorter) / len(longer) >= 0.6


def join_texts(texts: list[str]) -> str:
    return "\n".join(text for text in texts if text)


def _offline_tokens(text: str) -> list[str]:
    """返回确定且可逆的离线 token 近似结果。

    每个中日韩统一表意文字按一个 token 处理。其他字符按最多四个 UTF-8 字节分组，
    且不会拆开单个 Unicode 码位。
    """
    tokens: list[str] = []
    pending: list[str] = []
    pending_bytes = 0

    def flush() -> None:
        nonlocal pending, pending_bytes
        if pending:
            tokens.append("".join(pending))
        pending = []
        pending_bytes = 0

    for character in text:
        if "\u3400" <= character <= "\u9fff":
            flush()
            tokens.append(character)
            continue

        byte_count = len(character.encode("utf-8"))
        if pending and pending_bytes + byte_count > 4:
            flush()
        pending.append(character)
        pending_bytes += byte_count
        if pending_bytes >= 4:
            flush()

    flush()
    return tokens


def _split_encoded_tokens(
    encoder: tiktoken.Encoding,
    token_ids: list[int],
    chunk_token_size: int,
) -> list[str]:
    """仅在同时满足 UTF-8 完整性的 token 边界处切分。"""
    token_bytes = encoder.decode_tokens_bytes(token_ids)
    valid_boundaries = [0]
    undecoded = b""
    for index, value in enumerate(token_bytes, start=1):
        undecoded += value
        try:
            undecoded.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            continue
        valid_boundaries.append(index)
        undecoded = b""

    chunks: list[str] = []
    start = 0
    while start < len(token_ids):
        limit = start + chunk_token_size
        boundary_index = bisect_right(valid_boundaries, limit) - 1
        end = valid_boundaries[boundary_index]
        if end <= start:
            end = valid_boundaries[bisect_right(valid_boundaries, start)]
        chunks.append(
            b"".join(token_bytes[start:end]).decode(
                "utf-8",
                errors="strict",
            )
        )
        start = end
    return chunks


__all__ = [
    "DEFAULT_CHUNK_TOKEN_SIZE",
    "SourcedTextPart",
    "count_tokens",
    "join_texts",
    "normalize_text",
    "resolve_outline_levels",
    "split_blocks_fixed",
    "split_text_fixed",
    "validate_chunk_token_size",
]
