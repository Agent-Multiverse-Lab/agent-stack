"""Embedding 服务契约测试。"""

import unittest

from langchain_core.embeddings import Embeddings

from src.knowledge.embedding_service import EmbeddingService


class FakeEmbeddings(Embeddings):
    """记录批次并返回可控向量。"""

    def __init__(self, dimension: int = 3) -> None:
        self.dimension = dimension
        self.batches: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """同步生成固定维度向量。"""
        self.batches.append(texts)
        return [[float(index)] * self.dimension for index, _ in enumerate(texts)]

    def embed_query(self, text: str) -> list[float]:
        """同步生成固定维度查询向量。"""
        return [1.0] * self.dimension

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """异步生成固定维度向量。"""
        return self.embed_documents(texts)

    async def aembed_query(self, text: str) -> list[float]:
        """异步生成固定维度查询向量。"""
        return self.embed_query(text)


class InvalidEmbeddings(FakeEmbeddings):
    """返回非法数值的测试模型。"""

    async def aembed_query(self, text: str) -> list[float]:
        """返回包含 NaN 的查询向量。"""
        return [1.0, float("nan")]


class EmbeddingServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_embed_texts_uses_explicit_batches(self) -> None:
        model = FakeEmbeddings()
        service = EmbeddingService(
            model,
            model_spec="mock/test",
            batch_size=2,
        )

        vectors = await service.embed_texts(["a", "b", "c"])

        self.assertEqual([2, 1], [len(batch) for batch in model.batches])
        self.assertEqual(3, len(vectors))
        self.assertEqual(3, service.dimension)

    async def test_rejects_bound_dimension_mismatch(self) -> None:
        service = EmbeddingService(
            FakeEmbeddings(dimension=2),
            model_spec="mock/test",
            batch_size=2,
            expected_dimension=3,
        )

        with self.assertRaisesRegex(ValueError, "维度"):
            await service.embed_query("query")

    async def test_rejects_non_finite_vector(self) -> None:
        service = EmbeddingService(
            InvalidEmbeddings(),
            model_spec="mock/test",
            batch_size=2,
        )

        with self.assertRaisesRegex(ValueError, "非有限"):
            await service.embed_query("query")


if __name__ == "__main__":
    unittest.main()
