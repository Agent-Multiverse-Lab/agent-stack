"""实现无 I/O 的分块级检索指标。"""

from __future__ import annotations

from collections.abc import Collection, Sequence

from .types import KMetrics


class RetrievalMetrics:
    """封装分块级检索指标的计算规则。"""

    @staticmethod
    def _validate_k(k: int) -> None:
        """校验指标计算使用的 K。"""
        if isinstance(k, bool) or not isinstance(k, int) or k <= 0:
            raise ValueError("K 必须是正整数")

    @staticmethod
    def _validate_relevant_ids(
        relevant_chunk_ids: Collection[str],
    ) -> set[str]:
        """校验 Ground Truth 并转换为集合。"""
        if not relevant_chunk_ids:
            raise ValueError("Ground Truth 不能是空集合")
        relevant = set(relevant_chunk_ids)
        if len(relevant) != len(relevant_chunk_ids):
            raise ValueError("Ground Truth 不能包含重复 chunk_id")
        if any(not isinstance(chunk_id, str) or not chunk_id.strip() for chunk_id in relevant):
            raise ValueError("Ground Truth 中的 chunk_id 必须是非空字符串")
        return relevant

    @classmethod
    def _unique_prefix(
        cls,
        retrieved_chunk_ids: Sequence[str],
        k: int,
    ) -> list[str]:
        """按首次出现顺序去重并截取前 K 个结果。"""
        cls._validate_k(k)
        unique_ids: list[str] = []
        seen: set[str] = set()
        for chunk_id in retrieved_chunk_ids:
            if not isinstance(chunk_id, str) or not chunk_id.strip():
                raise ValueError("检索结果中的 chunk_id 必须是非空字符串")
            if chunk_id not in seen:
                seen.add(chunk_id)
                unique_ids.append(chunk_id)
        return unique_ids[:k]

    def hit_at_k(
        self,
        relevant_chunk_ids: Collection[str],
        retrieved_chunk_ids: Sequence[str],
        k: int,
    ) -> int:
        """计算单条查询的 Hit@K。"""
        relevant = self._validate_relevant_ids(relevant_chunk_ids)
        retrieved = self._unique_prefix(retrieved_chunk_ids, k)
        return int(bool(relevant.intersection(retrieved)))

    def precision_at_k(
        self,
        relevant_chunk_ids: Collection[str],
        retrieved_chunk_ids: Sequence[str],
        k: int,
    ) -> float:
        """计算单条查询的 Precision@K。"""
        relevant = self._validate_relevant_ids(relevant_chunk_ids)
        retrieved = self._unique_prefix(retrieved_chunk_ids, k)
        if not retrieved:
            return 0.0
        return len(relevant.intersection(retrieved)) / len(retrieved)

    def recall_at_k(
        self,
        relevant_chunk_ids: Collection[str],
        retrieved_chunk_ids: Sequence[str],
        k: int,
    ) -> float:
        """计算单条查询的 Recall@K。"""
        relevant = self._validate_relevant_ids(relevant_chunk_ids)
        retrieved = self._unique_prefix(retrieved_chunk_ids, k)
        return len(relevant.intersection(retrieved)) / len(relevant)

    def f1_at_k(
        self,
        relevant_chunk_ids: Collection[str],
        retrieved_chunk_ids: Sequence[str],
        k: int,
    ) -> float:
        """计算单条查询的 F1@K。"""
        precision = self.precision_at_k(
            relevant_chunk_ids,
            retrieved_chunk_ids,
            k,
        )
        recall = self.recall_at_k(
            relevant_chunk_ids,
            retrieved_chunk_ids,
            k,
        )
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    def calculate_query_metrics(
        self,
        relevant_chunk_ids: Collection[str],
        retrieved_chunk_ids: Sequence[str],
        k: int,
    ) -> KMetrics:
        """一次计算单条查询在 K 下的全部指标。"""
        relevant = self._validate_relevant_ids(relevant_chunk_ids)
        retrieved = self._unique_prefix(retrieved_chunk_ids, k)
        matched_count = len(relevant.intersection(retrieved))
        precision = matched_count / len(retrieved) if retrieved else 0.0
        recall = matched_count / len(relevant)
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return KMetrics(
            k=k,
            hit=int(matched_count > 0),
            precision=precision,
            recall=recall,
            f1=f1,
        )
