from __future__ import annotations

import unittest
from unittest import mock

import numpy as np

from src.knowledge.flow import (
    DocumentBlock,
    DocumentChunk,
    ParsedDocument,
    Pipeline,
    RaptorPostProcessor,
    TitleChunker,
)


class _StubParser:
    """为 Pipeline 测试返回固定解析结果。"""

    async def parse(
        self,
        _: object,
        *,
        file_name: str,
    ) -> ParsedDocument:
        """返回包含单个正文块的文档。"""
        return ParsedDocument(
            name=file_name,
            suffix=".txt",
            blocks=[DocumentBlock(text="agent runtime agent memory")],
        )


class _StubEmbeddingProvider:
    """返回固定 Chunk Embedding 供 RAPTOR 聚类测试使用。"""

    async def aembed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """按输入数量返回固定三维向量。"""
        return [
            [float(index), float(index % 2), 1.0]
            for index, _ in enumerate(texts)
        ]


class KnowledgeFlowTest(unittest.IsolatedAsyncioTestCase):
    """验证文档处理算法及 Pipeline 分阶段入口。"""

    def test_title_chunker_prefers_outline_bigram_levels(self) -> None:
        """PDF outline 有效命中时应优先于正则标题层级。"""
        document = ParsedDocument(
            name="outline.pdf",
            suffix=".pdf",
            json_result=[
                {"text": "第1章 总则", "doc_type_kwd": "text"},
                {"text": "适用范围", "doc_type_kwd": "text"},
            ],
            outlines=[("第1章 总则", 1, 0)],
        )

        chunks = TitleChunker(
            method="group",
            target_level=2,
            chunk_token_size=128,
        ).chunk(document)

        self.assertTrue(chunks)
        self.assertEqual(2, chunks[0].metadata["heading_level"])
        self.assertEqual(["第1章 总则"], chunks[0].metadata["heading_path"])

    def test_title_chunkers_share_regex_frequency_resolution(self) -> None:
        """Group 与 Hierarchy 应复用同一套正则频率层级解析。"""
        document = ParsedDocument(
            name="chapters.txt",
            suffix=".txt",
            blocks=[
                DocumentBlock(text="第1章 总则"),
                DocumentBlock(text="第一章正文"),
                DocumentBlock(text="第2章 附则"),
                DocumentBlock(text="第二章正文"),
            ],
        )

        for method in ("group", "hierarchy"):
            with self.subTest(method=method):
                chunks = TitleChunker(
                    method=method,  # type: ignore[arg-type]
                    target_level=1,
                    chunk_token_size=128,
                ).chunk(document)
                self.assertEqual(
                    [["第1章 总则"], ["第2章 附则"]],
                    [chunk.metadata["heading_path"] for chunk in chunks],
                )

    @mock.patch(
        "src.knowledge.flow.post_processor.umap.UMAP.fit_transform"
    )
    async def test_raptor_post_processor_uses_gmm_clusters(
        self,
        fit_transform: mock.Mock,
    ) -> None:
        """RAPTOR 后处理应按 UMAP 与 GMM 结果写入聚类 metadata。"""
        fit_transform.return_value = np.asarray(
            [
                [0.0, 0.0],
                [0.1, 0.0],
                [0.0, 0.1],
                [0.1, 0.1],
                [0.2, 0.1],
                [10.0, 10.0],
                [10.1, 10.0],
                [10.0, 10.1],
                [10.1, 10.1],
                [10.2, 10.1],
            ],
            dtype=np.float64,
        )
        chunks = [
            DocumentChunk(text=f"chunk {index}")
            for index in range(10)
        ]

        result = await RaptorPostProcessor(
            _StubEmbeddingProvider(),
            max_clusters=2,
            small_layer_collapse=2,
        ).process(chunks)

        self.assertIs(result, chunks)
        self.assertEqual(
            {0, 1},
            {
                chunk.metadata["raptor_cluster_id"]
                for chunk in result
            },
        )
        self.assertTrue(
            all(
                0 <= chunk.metadata["raptor_cluster_probability"] <= 1
                for chunk in result
            )
        )
        fit_transform.assert_called_once()

    async def test_pipeline_separates_parsing_and_chunking(self) -> None:
        """解析完成后必须由调用方显式触发分块。"""
        pipeline = Pipeline(parser=_StubParser())  # type: ignore[arg-type]

        document = await pipeline.parse_document(
            b"content",
            file_name="sample.txt",
        )
        chunks = pipeline.chunk_document(
            document,
            chunker="token",
        )

        self.assertEqual("sample.txt", document.name)
        self.assertTrue(chunks)
        self.assertFalse(hasattr(pipeline, "run"))


if __name__ == "__main__":
    unittest.main()
