from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Literal

BlockKind = Literal["text", "title", "table", "image"]


@dataclass(slots=True)
class DocumentBlock:
    text: str
    kind: BlockKind = "text"
    heading_level: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParsedDocument:
    name: str
    suffix: str
    blocks: list[DocumentBlock] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    markdown: str = ""
    json_result: list[dict[str, Any]] | None = field(default=None, repr=False)
    file_source: str | bytes | Path | BinaryIO | None = field(default=None, repr=False)
    outlines: list[tuple[str, int, int]] = field(default_factory=list, repr=False)


@dataclass(slots=True)
class DocumentChunk:
    text: str
    kind: BlockKind = "text"
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "BlockKind",
    "DocumentBlock",
    "DocumentChunk",
    "ParsedDocument",
]
