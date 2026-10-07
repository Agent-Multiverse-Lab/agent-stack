import unittest

from src.agents.agent_library.subagents.satellite import SATELLITE_AGENT, SatelliteEvidence, SatelliteReport


class SatelliteAgentContractTest(unittest.TestCase):
    def test_report_supports_single_and_multi_temporal_tasks(self) -> None:
        evidence = SatelliteEvidence(
            asset_id="scene-001",
            source="catalog-a",
            evidence="工具返回该影像覆盖目标区域。",
        )
        for task_type in ("catalog_search", "single_temporal", "multi_temporal"):
            with self.subTest(task_type=task_type):
                report = SatelliteReport(
                    task_type=task_type,
                    summary="完成有界分析。",
                    evidence=[evidence],
                )
                self.assertEqual(report.task_type, task_type)

    def test_prompt_routes_temporal_modes_to_tools(self) -> None:
        prompt = SATELLITE_AGENT.context["system_prompt"]
        self.assertIn("单时相解译和多时相变化分析", prompt)
        self.assertIn("根据任务选择合适的工具组合", prompt)
        self.assertIn("多个数据源", prompt)
        self.assertIn("不生成不存在的影像", prompt)
