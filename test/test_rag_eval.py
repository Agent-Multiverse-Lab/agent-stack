"""RAG 检索评估器的确定性单元测试。"""

import unittest

from src.knowledge.rag_eval import (
    RetrievalDataset,
    RetrievalEvaluator,
    RetrievalMetrics,
)


def _dataset() -> RetrievalDataset:
    """构造包含 validation 和 test 的最小评测集。"""
    return RetrievalDataset.from_dict(
        {
            "dataset_id": "demo",
            "dataset_version": "v1",
            "corpus_version": "2026-08-03",
            "uid": "user-1",
            "kb_id": "kb-1",
            "samples": [
                {
                    "query_id": "q-validation",
                    "query": "validation query",
                    "split": "validation",
                    "relevant_chunk_ids": ["chunk-a", "chunk-b"],
                },
                {
                    "query_id": "q-test",
                    "query": "test query",
                    "split": "test",
                    "relevant_chunk_ids": ["chunk-a"],
                },
            ],
        }
    )


class RagEvalMetricsTest(unittest.TestCase):
    """验证指标公式和去重口径。"""

    def test_metrics_cover_full_partial_zero_duplicate_and_short_results(self) -> None:
        """指标应按去重后的实际返回结果计算。"""
        metrics = RetrievalMetrics()
        relevant = ["a", "b"]
        retrieved = ["a", "a", "noise"]

        self.assertEqual(1, metrics.hit_at_k(relevant, retrieved, 1))
        self.assertEqual(1.0, metrics.precision_at_k(relevant, retrieved, 1))
        self.assertEqual(0.5, metrics.recall_at_k(relevant, retrieved, 1))
        self.assertAlmostEqual(2 / 3, metrics.f1_at_k(relevant, retrieved, 1))

        self.assertEqual(1, metrics.hit_at_k(relevant, retrieved, 5))
        self.assertAlmostEqual(
            0.5,
            metrics.precision_at_k(relevant, retrieved, 5),
        )
        self.assertAlmostEqual(
            0.5,
            metrics.recall_at_k(relevant, retrieved, 5),
        )
        self.assertEqual(0.5, metrics.f1_at_k(relevant, retrieved, 5))

        self.assertEqual(0, metrics.hit_at_k(relevant, ["noise"], 1))
        self.assertEqual(0.0, metrics.precision_at_k(relevant, [], 3))
        self.assertEqual(0.0, metrics.recall_at_k(relevant, ["noise"], 3))
        self.assertEqual(0.0, metrics.f1_at_k(relevant, ["noise"], 3))

    def test_calculate_query_metrics_returns_all_values(self) -> None:
        """批量指标函数应与单项公式一致。"""
        metrics = RetrievalMetrics().calculate_query_metrics(["a"], ["a"], 1)

        self.assertEqual(1, metrics.hit)
        self.assertEqual(1.0, metrics.precision)
        self.assertEqual(1.0, metrics.recall)
        self.assertEqual(1.0, metrics.f1)

    def test_invalid_ground_truth_is_rejected(self) -> None:
        """空 Ground Truth 和重复标注不能进入评估。"""
        metrics = RetrievalMetrics()
        with self.assertRaises(ValueError):
            metrics.calculate_query_metrics([], ["a"], 1)
        with self.assertRaises(ValueError):
            metrics.calculate_query_metrics(["a", "a"], ["a"], 1)


class RagEvalEvaluatorTest(unittest.IsolatedAsyncioTestCase):
    """验证单次检索、去重、宏平均和 Top-K 选择。"""

    async def test_retrieves_once_and_selects_best_f1(self) -> None:
        """多个 K 应复用每条查询的一次最大 K 检索。"""
        calls: list[tuple[str, int]] = []

        async def retrieve(query: str, limit: int):
            calls.append((query, limit))
            return [
                {
                    "id": "row-a",
                    "distance": 0.1,
                    "entity": {"chunk_id": "chunk-a", "file_id": "file-1"},
                },
                {
                    "id": "duplicate-row",
                    "distance": 0.2,
                    "entity": {"chunk_id": "chunk-a", "file_id": "file-1"},
                },
                {
                    "id": "row-b",
                    "distance": 0.3,
                    "entity": {"chunk_id": "chunk-b", "file_id": "file-1"},
                },
            ]

        report = await RetrievalEvaluator(
            retrieve=retrieve,
            ks=[1, 3],
        ).evaluate(_dataset())

        self.assertEqual(
            [
                ("validation query", 3),
                ("test query", 3),
            ],
            calls,
        )
        validation_query = report.queries[0]
        validation_summary = next(item for item in report.summary_by_k if item.split == "validation" and item.k == 1)
        self.assertEqual(1, validation_summary.query_count)
        self.assertEqual(1.0, validation_summary.precision)
        self.assertEqual(0.5, validation_summary.recall)
        self.assertEqual(
            ("chunk-a", "chunk-b"),
            validation_query.retrieved_chunk_ids,
        )
        self.assertEqual(
            (1, 3),
            tuple(hit.rank for hit in validation_query.retrieved_hits),
        )
        self.assertEqual(
            ("chunk-a", "chunk-b"),
            validation_query.matched_chunk_ids,
        )
        self.assertEqual(3, report.selection.recommended_top_k)
        self.assertEqual(3, report.test_result.k)

    async def test_f1_tie_selects_smaller_k(self) -> None:
        """validation 的 F1 并列时应选择更小的 K。"""
        dataset = RetrievalDataset.from_dict(
            {
                "dataset_id": "demo",
                "dataset_version": "v1",
                "corpus_version": "c1",
                "uid": "u1",
                "kb_id": "kb1",
                "samples": [
                    {
                        "query_id": "q1",
                        "query": "query",
                        "split": "validation",
                        "relevant_chunk_ids": ["a"],
                    }
                ],
            }
        )

        async def retrieve(query: str, limit: int):
            return [
                {"id": "a", "entity": {"chunk_id": "a"}},
                {"id": "noise", "entity": {"chunk_id": "noise"}},
            ]

        report = await RetrievalEvaluator(
            retrieve=retrieve,
            ks=[1, 3],
        ).evaluate(dataset)

        self.assertEqual(1, report.selection.recommended_top_k)

    async def test_min_recall_filters_candidates_and_falls_back(self) -> None:
        """召回目标未达成时仍选择最高 F1 并标记失败。"""
        dataset = RetrievalDataset.from_dict(
            {
                "dataset_id": "demo",
                "dataset_version": "v1",
                "corpus_version": "c1",
                "uid": "u1",
                "kb_id": "kb1",
                "samples": [
                    {
                        "query_id": "q1",
                        "query": "query",
                        "split": "validation",
                        "relevant_chunk_ids": ["a", "b"],
                    }
                ],
            }
        )

        async def retrieve(query: str, limit: int):
            return [{"id": "noise", "entity": {"chunk_id": "noise"}}]

        report = await RetrievalEvaluator(
            retrieve=retrieve,
            ks=[1, 3],
            min_recall=0.8,
        ).evaluate(dataset)

        self.assertFalse(report.selection.recall_target_met)
        self.assertEqual(1, report.selection.recommended_top_k)

    async def test_missing_chunk_id_is_rejected(self) -> None:
        """命中同时缺少 chunk_id 和 id 时必须失败。"""

        async def retrieve(query: str, limit: int):
            return [{"distance": 0.1, "entity": {"file_id": "file-1"}}]

        with self.assertRaisesRegex(ValueError, "chunk_id"):
            await RetrievalEvaluator(
                retrieve=retrieve,
                ks=[1],
            ).evaluate(_dataset())

    async def test_invalid_k_and_duplicate_query_id_are_rejected(self) -> None:
        """非法 K 和重复 query_id 不能生成报告。"""

        async def retrieve(query: str, limit: int):
            return []

        with self.assertRaises(ValueError):
            RetrievalEvaluator(retrieve=retrieve, ks=[0])

        with self.assertRaises(ValueError):
            RetrievalDataset.from_dict(
                {
                    "dataset_id": "demo",
                    "dataset_version": "v1",
                    "corpus_version": "c1",
                    "uid": "u1",
                    "kb_id": "kb1",
                    "samples": [
                        {
                            "query_id": "same",
                            "query": "one",
                            "split": "validation",
                            "relevant_chunk_ids": ["a"],
                        },
                        {
                            "query_id": "same",
                            "query": "two",
                            "split": "test",
                            "relevant_chunk_ids": ["a"],
                        },
                    ],
                }
            )


if __name__ == "__main__":
    unittest.main()
