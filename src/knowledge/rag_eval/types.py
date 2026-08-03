"""定义 RAG 检索评估的数据结构和输入校验。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

VALID_SPLITS = frozenset({"validation", "test"})
MAX_SEARCH_LIMIT = 100

type AsyncRetrieve = Callable[[str, int], Awaitable[Sequence[Any]]]


def _required_text(value: Any, field_name: str) -> str:
    """校验并返回非空文本字段。"""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 必须是非空字符串")
    return value.strip()


def _chunk_ids(value: Any, field_name: str) -> tuple[str, ...]:
    """校验分块 ID 列表并保留人工标注顺序。"""
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} 必须是字符串列表")
    ids = tuple(_required_text(item, f"{field_name} 的元素") for item in value)
    if not ids:
        raise ValueError(f"{field_name} 不能为空")
    if len(ids) != len(set(ids)):
        raise ValueError(f"{field_name} 不能包含重复 ID")
    return ids


@dataclass(frozen=True, slots=True)
class RetrievalSample:
    """表示一条带人工 Ground Truth 的检索查询。"""

    query_id: str
    query: str
    split: str
    relevant_chunk_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        """校验查询标识、划分和人工标注。"""
        object.__setattr__(self, "query_id", _required_text(self.query_id, "query_id"))
        object.__setattr__(self, "query", _required_text(self.query, "query"))
        split = _required_text(self.split, "split")
        if split not in VALID_SPLITS:
            raise ValueError("split 只能是 validation 或 test")
        object.__setattr__(self, "split", split)
        object.__setattr__(
            self,
            "relevant_chunk_ids",
            _chunk_ids(self.relevant_chunk_ids, "relevant_chunk_ids"),
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RetrievalSample:
        """从 JSON 对象构造一条评测查询。"""
        if not isinstance(payload, Mapping):
            raise ValueError("samples 的每一项必须是对象")
        return cls(
            query_id=payload.get("query_id"),
            query=payload.get("query"),
            split=payload.get("split"),
            relevant_chunk_ids=payload.get("relevant_chunk_ids"),
        )

    def to_dict(self) -> dict[str, Any]:
        """将查询转换为可序列化字典。"""
        return {
            "query_id": self.query_id,
            "query": self.query,
            "split": self.split,
            "relevant_chunk_ids": list(self.relevant_chunk_ids),
        }


@dataclass(frozen=True, slots=True)
class RetrievalDataset:
    """表示绑定单一用户、知识库和语料版本的检索评测集。"""

    dataset_id: str
    dataset_version: str
    corpus_version: str
    uid: str
    kb_id: str
    samples: tuple[RetrievalSample, ...]

    def __post_init__(self) -> None:
        """校验数据集元数据和查询 ID 唯一性。"""
        for field_name in (
            "dataset_id",
            "dataset_version",
            "corpus_version",
            "uid",
            "kb_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _required_text(getattr(self, field_name), field_name),
            )

        if isinstance(self.samples, (str, bytes)) or not isinstance(self.samples, Sequence):
            raise ValueError("samples 必须是列表")
        samples = tuple(sample if isinstance(sample, RetrievalSample) else RetrievalSample.from_dict(sample) for sample in self.samples)
        if not samples:
            raise ValueError("samples 不能为空")
        query_ids = [sample.query_id for sample in samples]
        if len(query_ids) != len(set(query_ids)):
            raise ValueError("query_id 在数据集内必须唯一")
        object.__setattr__(self, "samples", samples)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RetrievalDataset:
        """从 JSON 对象构造并校验评测集。"""
        if not isinstance(payload, Mapping):
            raise ValueError("评测集根节点必须是对象")
        return cls(
            dataset_id=payload.get("dataset_id"),
            dataset_version=payload.get("dataset_version"),
            corpus_version=payload.get("corpus_version"),
            uid=payload.get("uid"),
            kb_id=payload.get("kb_id"),
            samples=payload.get("samples"),
        )

    def to_dict(self) -> dict[str, Any]:
        """将评测集转换为可序列化字典。"""
        return {
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "corpus_version": self.corpus_version,
            "uid": self.uid,
            "kb_id": self.kb_id,
            "samples": [sample.to_dict() for sample in self.samples],
        }


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    """保存去重后的生产检索命中及其原始排名信息。"""

    chunk_id: str
    rank: int
    distance: float | None = None
    file_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """将检索命中转换为可序列化字典。"""
        return {
            "chunk_id": self.chunk_id,
            "rank": self.rank,
            "distance": self.distance,
            "file_id": self.file_id,
        }


@dataclass(frozen=True, slots=True)
class KMetrics:
    """保存一条查询在一个 K 下的四项指标。"""

    k: int
    hit: int
    precision: float
    recall: float
    f1: float

    def to_dict(self) -> dict[str, Any]:
        """将单查询指标转换为可序列化字典。"""
        return {
            "k": self.k,
            "hit": self.hit,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
        }


@dataclass(frozen=True, slots=True)
class QueryEvaluation:
    """保存一条查询的去重结果、命中集合和各 K 指标。"""

    query_id: str
    split: str
    query: str
    relevant_chunk_ids: tuple[str, ...]
    retrieved_chunk_ids: tuple[str, ...]
    matched_chunk_ids: tuple[str, ...]
    retrieved_hits: tuple[RetrievalHit, ...]
    metrics_by_k: tuple[KMetrics, ...]

    def to_dict(self) -> dict[str, Any]:
        """将逐查询评估结果转换为可序列化字典。"""
        return {
            "query_id": self.query_id,
            "split": self.split,
            "query": self.query,
            "relevant_chunk_ids": list(self.relevant_chunk_ids),
            "retrieved_chunk_ids": list(self.retrieved_chunk_ids),
            "matched_chunk_ids": list(self.matched_chunk_ids),
            "retrieved_hits": [hit.to_dict() for hit in self.retrieved_hits],
            "metrics_by_k": [metrics.to_dict() for metrics in self.metrics_by_k],
        }


@dataclass(frozen=True, slots=True)
class MetricSummary:
    """保存一个数据划分在一个 K 下的宏平均指标。"""

    split: str
    k: int
    query_count: int
    hit_rate: float
    precision: float
    recall: float
    f1: float

    def to_dict(self) -> dict[str, Any]:
        """将宏平均指标转换为可序列化字典。"""
        return {
            "split": self.split,
            "k": self.k,
            "query_count": self.query_count,
            "hit_rate": self.hit_rate,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
        }


@dataclass(slots=True)
class RunMetadata:
    """保存一次评估运行的语料和 Embedding 契约。"""

    dataset_id: str
    dataset_version: str
    corpus_version: str
    uid: str
    kb_id: str
    ks: tuple[int, ...]
    embedding_model_spec: str | None = None
    embedding_dimension: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """将运行元数据转换为可序列化字典。"""
        return {
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "corpus_version": self.corpus_version,
            "uid": self.uid,
            "kb_id": self.kb_id,
            "embedding_model_spec": self.embedding_model_spec,
            "embedding_dimension": self.embedding_dimension,
            "ks": list(self.ks),
        }


@dataclass(frozen=True, slots=True)
class SelectionResult:
    """保存基于 validation 指标选出的全局 Top-K。"""

    recommended_top_k: int
    min_recall: float | None
    recall_target_met: bool
    selected_on: str = "validation"

    def to_dict(self) -> dict[str, Any]:
        """将 Top-K 选择结果转换为可序列化字典。"""
        return {
            "recommended_top_k": self.recommended_top_k,
            "min_recall": self.min_recall,
            "recall_target_met": self.recall_target_met,
            "selected_on": self.selected_on,
        }


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationReport:
    """保存完整检索评估报告。"""

    run: RunMetadata
    summary_by_k: tuple[MetricSummary, ...]
    selection: SelectionResult
    test_result: MetricSummary | None
    queries: tuple[QueryEvaluation, ...]

    def to_dict(self) -> dict[str, Any]:
        """将完整报告转换为可序列化字典。"""
        return {
            "run": self.run.to_dict(),
            "summary_by_k": [summary.to_dict() for summary in self.summary_by_k],
            "selection": self.selection.to_dict(),
            "test_result": (self.test_result.to_dict() if self.test_result is not None else None),
            "queries": [query.to_dict() for query in self.queries],
        }
