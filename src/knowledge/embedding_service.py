"""知识文本向量化服务。"""

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite

from langchain_core.embeddings import Embeddings

from src.knowledge.flow.types import DocumentChunk


@dataclass(slots=True, frozen=True)
class EmbeddedChunk:
    """保存分块及其已校验向量。"""

    chunk: DocumentChunk
    embedding: list[float]


class EmbeddingService:
    """对注入模型执行批量向量化并验证向量契约。"""

    def __init__(
        self,
        embedding_model: Embeddings,
        *,
        model_spec: str,
        batch_size: int,
        expected_dimension: int | None = None,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("Embedding batch_size 必须大于 0")
        if expected_dimension is not None and expected_dimension <= 0:
            raise ValueError("Embedding expected_dimension 必须大于 0")

        self.embedding_model = embedding_model
        self.model_spec = model_spec
        self.batch_size = batch_size
        self.expected_dimension = expected_dimension
        self._observed_dimension: int | None = None

    @property
    def dimension(self) -> int | None:
        """返回当前已验证的向量维度。"""
        return self.expected_dimension or self._observed_dimension

    async def embed_chunks(
        self,
        chunks: Sequence[DocumentChunk],
    ) -> list[EmbeddedChunk]:
        """过滤空分块并按配置批量生成向量。"""
        selected_chunks = [chunk for chunk in chunks if chunk.text.strip()]
        vectors = await self.embed_texts(
            [chunk.text for chunk in selected_chunks]
        )
        return [
            EmbeddedChunk(chunk=chunk, embedding=vector)
            for chunk, vector in zip(selected_chunks, vectors, strict=True)
        ]

    async def embed_texts(
        self,
        texts: Sequence[str],
    ) -> list[list[float]]:
        """按固定批大小编码非空文本。"""
        normalized_texts = [text.strip() for text in texts]
        if any(not text for text in normalized_texts):
            raise ValueError("Embedding 文本不能为空")

        vectors: list[list[float]] = []
        for start in range(0, len(normalized_texts), self.batch_size):
            batch = normalized_texts[start : start + self.batch_size]
            batch_vectors = await self.embedding_model.aembed_documents(batch)
            vectors.extend(self._validate_vectors(batch_vectors, len(batch)))
        return vectors

    async def embed_query(self, query: str) -> list[float]:
        """生成并验证单条查询向量。"""
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Embedding 查询文本不能为空")

        vector = await self.embedding_model.aembed_query(normalized_query)
        return self._validate_vectors([vector], 1)[0]

    async def detect_dimension(self) -> int:
        """通过一次真实查询验证连接并探测模型维度。"""
        await self.embed_query("embedding dimension probe")
        if self.dimension is None:
            raise RuntimeError("Embedding 模型未返回可用维度")
        return self.dimension

    def _validate_vectors(
        self,
        vectors: Sequence[Sequence[float]],
        expected_count: int,
    ) -> list[list[float]]:
        """校验数量、维度和数值有效性。"""
        if len(vectors) != expected_count:
            raise ValueError(
                "Embedding 返回数量与输入数量不一致："
                f"{len(vectors)} != {expected_count}"
            )

        validated: list[list[float]] = []
        for vector in vectors:
            normalized = [float(value) for value in vector]
            if not normalized:
                raise ValueError("Embedding 返回了空向量")
            if not all(isfinite(value) for value in normalized):
                raise ValueError("Embedding 返回了非有限数值")

            dimension = len(normalized)
            required_dimension = self.dimension
            if required_dimension is not None and dimension != required_dimension:
                raise ValueError(
                    "Embedding 向量维度与知识库绑定不一致："
                    f"{dimension} != {required_dimension}"
                )
            if self._observed_dimension is None:
                self._observed_dimension = dimension
            elif dimension != self._observed_dimension:
                raise ValueError(
                    "Embedding 同一次运行返回了不同维度："
                    f"{dimension} != {self._observed_dimension}"
                )
            validated.append(normalized)
        return validated
