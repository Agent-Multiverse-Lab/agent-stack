from __future__ import annotations

import asyncio
from typing import Protocol

import numpy as np
import umap
from sklearn.mixture import GaussianMixture

from .types import DocumentChunk

_GMM_REG_COVAR = 1e-4


class EmbeddingProvider(Protocol):
    """提供文档分块向量的最小契约。"""

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量返回与输入文本顺序一致的向量。"""


class PostProcessor(Protocol):
    """文档分块后处理器的最小契约。"""

    async def process(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        """处理分块并返回可继续写入知识库的结果。"""


class RaptorPostProcessor:
    """实现 RAGFlow RAPTOR 的 UMAP 与 GMM 聚类阶段。"""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        *,
        max_clusters: int = 64,
        threshold: float = 0.1,
        random_state: int = 0,
        small_layer_collapse: int = 8,
    ) -> None:
        """初始化与 RAGFlow 默认配置一致的聚类参数。"""
        if max_clusters <= 0:
            raise ValueError("max_clusters 必须大于 0。")
        if not 0 <= threshold <= 1:
            raise ValueError("threshold 必须在 0 到 1 之间。")
        if small_layer_collapse <= 0:
            raise ValueError("small_layer_collapse 必须大于 0。")

        self._embedding_provider = embedding_provider
        self._max_clusters = max_clusters
        self._threshold = threshold
        self._random_state = random_state
        self._small_layer_collapse = small_layer_collapse

    async def process(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        """对 Chunk Embedding 聚类并写入 RAPTOR 聚类 metadata。"""
        if not chunks:
            return chunks

        if len(chunks) <= self._small_layer_collapse:
            labels = np.zeros(len(chunks), dtype=int)
            probabilities = np.ones(len(chunks), dtype=np.float64)
        else:
            raw_embeddings = await self._embedding_provider.aembed_documents(
                [chunk.text for chunk in chunks]
            )
            embeddings = np.asarray(raw_embeddings, dtype=np.float64)
            self._validate_embeddings(embeddings, len(chunks))
            labels, probabilities = await asyncio.to_thread(
                self._cluster,
                embeddings,
            )

        for chunk, label, probability in zip(
            chunks,
            labels,
            probabilities,
            strict=True,
        ):
            chunk.metadata = {
                **chunk.metadata,
                "raptor_cluster_id": int(label),
                "raptor_cluster_probability": round(float(probability), 6),
            }

        return chunks

    def _cluster(
        self,
        embeddings: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """按 RAGFlow 的 UMAP、BIC 和 GMM 顺序完成聚类。"""
        chunk_count = len(embeddings)
        n_neighbors = min(int((chunk_count - 1) ** 0.8), 100)
        reduced = umap.UMAP(
            n_neighbors=max(2, n_neighbors),
            n_components=min(12, chunk_count - 2),
            metric="cosine",
        ).fit_transform(embeddings)

        cluster_count = self._get_optimal_cluster_count(reduced)
        if cluster_count <= 1:
            return (
                np.zeros(chunk_count, dtype=int),
                np.ones(chunk_count, dtype=np.float64),
            )

        model = GaussianMixture(
            n_components=cluster_count,
            random_state=self._random_state,
            covariance_type="diag",
            reg_covar=_GMM_REG_COVAR,
        )
        model.fit(reduced)
        prediction_probabilities = model.predict_proba(reduced)

        labels: list[int] = []
        probabilities: list[float] = []
        for probability in prediction_probabilities:
            candidates = np.where(probability > self._threshold)[0]
            label = (
                int(candidates[0])
                if len(candidates)
                else int(np.argmax(probability))
            )
            labels.append(label)
            probabilities.append(float(probability[label]))

        unique_labels = np.unique(labels)
        label_map = {
            int(original): normalized
            for normalized, original in enumerate(unique_labels)
        }
        return (
            np.asarray([label_map[label] for label in labels], dtype=int),
            np.asarray(probabilities, dtype=np.float64),
        )

    def _get_optimal_cluster_count(self, embeddings: np.ndarray) -> int:
        """使用 RAGFlow 相同的最低 BIC 规则选择 GMM 聚类数。"""
        max_clusters = min(self._max_clusters, len(embeddings))
        if max_clusters <= 1:
            return 1

        candidates = range(1, max_clusters + 1)
        bic_scores = []
        for cluster_count in candidates:
            model = GaussianMixture(
                n_components=cluster_count,
                random_state=self._random_state,
                covariance_type="diag",
                reg_covar=_GMM_REG_COVAR,
            )
            model.fit(embeddings)
            bic_scores.append(model.bic(embeddings))

        return int(np.argmin(bic_scores)) + 1

    @staticmethod
    def _validate_embeddings(
        embeddings: np.ndarray,
        chunk_count: int,
    ) -> None:
        """校验向量数量、维度和数值有效性。"""
        if embeddings.ndim != 2:
            raise ValueError("Embedding Provider 必须返回二维向量列表。")
        if embeddings.shape[0] != chunk_count:
            raise ValueError("Embedding 数量必须与 DocumentChunk 数量一致。")
        if embeddings.shape[1] == 0:
            raise ValueError("Embedding 向量不能为空。")
        if not np.isfinite(embeddings).all():
            raise ValueError("Embedding 向量不能包含无穷值或 NaN。")


__all__ = ["EmbeddingProvider", "PostProcessor", "RaptorPostProcessor"]
