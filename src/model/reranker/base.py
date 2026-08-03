"""定义与模型提供商无关的检索重排契约。"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isfinite
from numbers import Real
from typing import Any


@dataclass(frozen=True, slots=True)
class RerankDocument:
    """表示一个待重排的业务文档。"""

    id: str
    text: str
    original_rank: int
    retrieval_score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RerankResult:
    """表示归一化后的单条重排结果。"""

    document: RerankDocument
    relevance_score: float
    rerank_rank: int


class RerankError(RuntimeError):
    """表示 Rerank Provider 请求或响应异常。"""


class BaseReranker(ABC):
    """校验通用输入并将 Provider 分数转换为稳定结果。"""

    async def arerank(
        self,
        query: str,
        documents: Sequence[RerankDocument],
        *,
        top_n: int,
    ) -> list[RerankResult]:
        """重排候选文档并返回稳定的相关性顺序。"""
        query_text = query.strip()
        if not query_text:
            raise ValueError("Rerank 查询不能为空")
        if isinstance(top_n, bool) or not isinstance(top_n, int) or top_n <= 0:
            raise ValueError("Rerank top_n 必须是正整数")

        candidates = tuple(documents)
        if not candidates:
            raise ValueError("Rerank 候选文档不能为空")
        self._validate_documents(candidates)

        result_count = min(top_n, len(candidates))
        scored_indices = tuple(
            await self._score(
                query_text,
                candidates,
                top_n=result_count,
            )
        )
        if len(scored_indices) != result_count:
            raise RerankError(
                "Rerank 返回数量与请求不一致："
                f"expected={result_count}, actual={len(scored_indices)}"
            )

        validated_scores = self._validate_scores(
            scored_indices,
            candidate_count=len(candidates),
        )
        validated_scores.sort(
            key=lambda item: (
                -item[1],
                candidates[item[0]].original_rank,
            )
        )
        return [
            RerankResult(
                document=candidates[index],
                relevance_score=score,
                rerank_rank=rank,
            )
            for rank, (index, score) in enumerate(
                validated_scores,
                start=1,
            )
        ]

    @abstractmethod
    async def _score(
        self,
        query: str,
        documents: Sequence[RerankDocument],
        *,
        top_n: int,
    ) -> Sequence[tuple[int, float]]:
        """调用具体 Provider 并返回输入索引及相关性分数。"""

    @staticmethod
    def _validate_documents(
        documents: Sequence[RerankDocument],
    ) -> None:
        """校验候选业务标识、正文和原始排名。"""
        document_ids: set[str] = set()
        original_ranks: set[int] = set()

        for document in documents:
            if not isinstance(document.id, str) or not document.id.strip():
                raise ValueError("Rerank 文档 ID 不能为空")
            if document.id in document_ids:
                raise ValueError(f"Rerank 文档 ID 重复：{document.id}")
            document_ids.add(document.id)

            if not isinstance(document.text, str) or not document.text.strip():
                raise ValueError(f"Rerank 文档正文不能为空：{document.id}")
            if (
                isinstance(document.original_rank, bool)
                or not isinstance(document.original_rank, int)
                or document.original_rank <= 0
            ):
                raise ValueError(
                    f"Rerank 原始排名必须是正整数：{document.id}"
                )
            if document.original_rank in original_ranks:
                raise ValueError(
                    f"Rerank 原始排名重复：{document.original_rank}"
                )
            original_ranks.add(document.original_rank)

            retrieval_score = document.retrieval_score
            if retrieval_score is not None and (
                isinstance(retrieval_score, bool)
                or not isinstance(retrieval_score, Real)
                or not isfinite(float(retrieval_score))
            ):
                raise ValueError(
                    f"Rerank 原始检索分数非法：{document.id}"
                )

    @staticmethod
    def _validate_scores(
        scored_indices: Sequence[tuple[int, float]],
        *,
        candidate_count: int,
    ) -> list[tuple[int, float]]:
        """校验 Provider 返回的索引和有限分数。"""
        seen_indices: set[int] = set()
        validated_scores: list[tuple[int, float]] = []

        for item in scored_indices:
            if not isinstance(item, tuple) or len(item) != 2:
                raise RerankError("Rerank 结果必须包含 index 和 score")

            index, score = item
            if (
                isinstance(index, bool)
                or not isinstance(index, int)
                or index < 0
                or index >= candidate_count
            ):
                raise RerankError(f"Rerank 返回了非法文档索引：{index}")
            if index in seen_indices:
                raise RerankError(f"Rerank 返回了重复文档索引：{index}")
            if (
                isinstance(score, bool)
                or not isinstance(score, Real)
                or not isfinite(float(score))
            ):
                raise RerankError(f"Rerank 返回了非法相关性分数：{score}")

            seen_indices.add(index)
            validated_scores.append((index, float(score)))

        return validated_scores


__all__ = [
    "BaseReranker",
    "RerankDocument",
    "RerankError",
    "RerankResult",
]
