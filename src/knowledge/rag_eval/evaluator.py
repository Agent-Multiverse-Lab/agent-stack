"""编排真实检索命中归一化、指标聚合和 Top-K 选择。"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from .metrics import RetrievalMetrics
from .types import (
    MAX_SEARCH_LIMIT,
    AsyncRetrieve,
    MetricSummary,
    QueryEvaluation,
    RetrievalDataset,
    RetrievalEvaluationReport,
    RetrievalHit,
    RetrievalSample,
    RunMetadata,
    SelectionResult,
)

_MISSING = object()


class RetrievalEvaluator:
    """封装一次检索评估运行的配置、归一化和报告聚合。"""

    def __init__(
        self,
        *,
        retrieve: AsyncRetrieve,
        ks: Sequence[int],
        min_recall: float | None = None,
    ) -> None:
        """绑定异步检索函数并校验评估参数。"""
        if not callable(retrieve):
            raise TypeError("retrieve 必须是可调用对象")
        self.retrieve = retrieve
        self.ks = self._validate_ks(ks)
        self._validate_min_recall(min_recall)
        self.min_recall = min_recall
        self.metrics = RetrievalMetrics()

    @staticmethod
    def _read_field(value: Any, field_name: str) -> Any:
        """兼容字典、Milvus Hit 和普通对象读取字段。"""
        if value is _MISSING or value is None:
            return _MISSING
        if isinstance(value, Mapping):
            return value.get(field_name, _MISSING)
        return getattr(value, field_name, _MISSING)

    @staticmethod
    def _text_or_none(value: Any) -> str | None:
        """把可选业务标识规范化为非空文本。"""
        if value is _MISSING or value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _distance_or_none(value: Any) -> float | None:
        """把可选相似度距离转换为有限浮点数。"""
        if value is _MISSING or value is None:
            return None
        distance = float(value)
        if not math.isfinite(distance):
            raise ValueError("检索结果 distance 必须是有限数值")
        return distance

    @staticmethod
    def normalize_hit(hit: Any, rank: int) -> RetrievalHit:
        """从生产命中读取 chunk_id、排名、距离和文件 ID。"""
        if rank <= 0:
            raise ValueError("检索结果 rank 必须从 1 开始")

        entity = RetrievalEvaluator._read_field(hit, "entity")
        chunk_id = RetrievalEvaluator._text_or_none(RetrievalEvaluator._read_field(entity, "chunk_id"))
        if chunk_id is None:
            chunk_id = RetrievalEvaluator._text_or_none(RetrievalEvaluator._read_field(hit, "chunk_id"))
        if chunk_id is None:
            chunk_id = RetrievalEvaluator._text_or_none(RetrievalEvaluator._read_field(hit, "id"))
        if chunk_id is None:
            raise ValueError(f"检索结果第 {rank} 条缺少 chunk_id，且没有可用的 hit.id")

        metadata = RetrievalEvaluator._read_field(entity, "metadata")
        file_id = RetrievalEvaluator._text_or_none(RetrievalEvaluator._read_field(entity, "file_id"))
        if file_id is None:
            file_id = RetrievalEvaluator._text_or_none(RetrievalEvaluator._read_field(metadata, "file_id"))
        if file_id is None:
            file_id = RetrievalEvaluator._text_or_none(RetrievalEvaluator._read_field(hit, "file_id"))

        return RetrievalHit(
            chunk_id=chunk_id,
            rank=rank,
            distance=RetrievalEvaluator._distance_or_none(RetrievalEvaluator._read_field(hit, "distance")),
            file_id=file_id,
        )

    @classmethod
    def normalize_hits(
        cls,
        hits: Sequence[Any],
        *,
        limit: int | None = None,
    ) -> tuple[RetrievalHit, ...]:
        """按首次出现位置去重生产命中并保留原始排名。"""
        if isinstance(hits, (str, bytes)) or not isinstance(hits, Sequence):
            raise ValueError("检索函数必须返回命中列表")
        normalized: list[RetrievalHit] = []
        seen: set[str] = set()
        max_items = len(hits) if limit is None else limit
        for index, raw_hit in enumerate(hits[:max_items], start=1):
            hit = cls.normalize_hit(raw_hit, index)
            if hit.chunk_id in seen:
                continue
            seen.add(hit.chunk_id)
            normalized.append(hit)
        return tuple(normalized)

    @staticmethod
    def _validate_ks(ks: Sequence[int]) -> tuple[int, ...]:
        """校验候选 K 的唯一性、范围和顺序。"""
        if isinstance(ks, (str, bytes)) or not isinstance(ks, Sequence):
            raise ValueError("ks 必须是正整数列表")
        values = tuple(ks)
        if not values:
            raise ValueError("ks 不能为空")
        if any(isinstance(k, bool) or not isinstance(k, int) for k in values):
            raise ValueError("ks 必须只包含整数")
        if any(k <= 0 or k > MAX_SEARCH_LIMIT for k in values):
            raise ValueError(f"ks 必须在 1 到 {MAX_SEARCH_LIMIT} 之间")
        if len(values) != len(set(values)):
            raise ValueError("ks 不能包含重复值")
        return values

    @staticmethod
    def _validate_min_recall(min_recall: float | None) -> None:
        """校验业务最低召回率。"""
        if min_recall is None:
            return
        if not isinstance(min_recall, (int, float)) or isinstance(
            min_recall,
            bool,
        ):
            raise ValueError("min_recall 必须是 0 到 1 之间的数值")
        if not math.isfinite(float(min_recall)) or not 0 <= min_recall <= 1:
            raise ValueError("min_recall 必须是 0 到 1 之间的数值")

    def _build_query_evaluation(
        self,
        sample: RetrievalSample,
        hits: tuple[RetrievalHit, ...],
    ) -> QueryEvaluation:
        """为一条查询构造去重结果和各 K 指标。"""
        retrieved_ids = tuple(hit.chunk_id for hit in hits)
        relevant_ids = set(sample.relevant_chunk_ids)
        matched_ids = tuple(chunk_id for chunk_id in retrieved_ids if chunk_id in relevant_ids)
        metrics_by_k = tuple(
            self.metrics.calculate_query_metrics(
                sample.relevant_chunk_ids,
                retrieved_ids,
                k,
            )
            for k in self.ks
        )
        return QueryEvaluation(
            query_id=sample.query_id,
            split=sample.split,
            query=sample.query,
            relevant_chunk_ids=sample.relevant_chunk_ids,
            retrieved_chunk_ids=retrieved_ids,
            matched_chunk_ids=matched_ids,
            retrieved_hits=hits,
            metrics_by_k=metrics_by_k,
        )

    @staticmethod
    def _summary_for(
        queries: Sequence[QueryEvaluation],
        split: str,
        k: int,
    ) -> MetricSummary | None:
        """对指定划分和 K 做查询级宏平均。"""
        selected = [query for query in queries if query.split == split]
        if not selected:
            return None
        metrics_by_query = {query.query_id: next(metrics for metrics in query.metrics_by_k if metrics.k == k) for query in selected}
        metrics = tuple(metrics_by_query.values())
        count = len(metrics)
        return MetricSummary(
            split=split,
            k=k,
            query_count=count,
            hit_rate=sum(item.hit for item in metrics) / count,
            precision=sum(item.precision for item in metrics) / count,
            recall=sum(item.recall for item in metrics) / count,
            f1=sum(item.f1 for item in metrics) / count,
        )

    def _select_top_k(
        self,
        summaries: Sequence[MetricSummary],
    ) -> SelectionResult:
        """按 validation 宏平均指标选择全局 Top-K。"""
        validation = [summary for summary in summaries if summary.split == "validation"]
        if not validation:
            raise ValueError("至少需要一条 validation 查询才能选择 recommended_top_k")

        if self.min_recall is None:
            candidates = validation
            target_met = True
        else:
            candidates = [summary for summary in validation if summary.recall >= self.min_recall]
            target_met = bool(candidates)
            if not candidates:
                candidates = validation

        selected = max(candidates, key=lambda summary: (summary.f1, -summary.k))
        return SelectionResult(
            recommended_top_k=selected.k,
            min_recall=self.min_recall,
            recall_target_met=target_met,
        )

    async def evaluate(
        self,
        dataset: RetrievalDataset,
    ) -> RetrievalEvaluationReport:
        """调用一次异步检索并生成完整的分块级评估报告。"""
        if not isinstance(dataset, RetrievalDataset):
            raise TypeError("dataset 必须是 RetrievalDataset")
        max_k = max(self.ks)

        query_evaluations: list[QueryEvaluation] = []
        for sample in dataset.samples:
            raw_hits = await self.retrieve(sample.query, max_k)
            hits = self.normalize_hits(raw_hits, limit=max_k)
            query_evaluations.append(self._build_query_evaluation(sample, hits))

        summaries: list[MetricSummary] = []
        for split in ("validation", "test"):
            for k in self.ks:
                summary = self._summary_for(query_evaluations, split, k)
                if summary is not None:
                    summaries.append(summary)

        selection = self._select_top_k(summaries)
        test_result = next(
            (summary for summary in summaries if summary.split == "test" and summary.k == selection.recommended_top_k),
            None,
        )
        return RetrievalEvaluationReport(
            run=RunMetadata(
                dataset_id=dataset.dataset_id,
                dataset_version=dataset.dataset_version,
                corpus_version=dataset.corpus_version,
                uid=dataset.uid,
                kb_id=dataset.kb_id,
                ks=self.ks,
            ),
            summary_by_k=tuple(summaries),
            selection=selection,
            test_result=test_result,
            queries=tuple(query_evaluations),
        )
