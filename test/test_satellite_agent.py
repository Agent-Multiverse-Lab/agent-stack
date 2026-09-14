from __future__ import annotations

import inspect
import unittest
from pathlib import Path

from src.agents.leaderagent.agent import LeaderAgent
from src.agents.manager import agent_manager
from src.agents.subagents.satelliteagent.context import SatelliteAgentContext
from src.agents.subagents.satelliteagent.prompt import build_prompt
from src.agents.subagents.satelliteagent.state import (
    SatelliteAgentReport,
    SatelliteEvidence,
)


class SatelliteAgentContractTest(unittest.TestCase):
    """验证 SatelliteAgent 的包结构、边界和运行注册。"""

    def test_package_uses_standard_subagent_structure(self) -> None:
        package_dir = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "agents"
            / "subagents"
            / "satelliteagent"
        )
        self.assertTrue(
            {
                "__init__.py",
                "agent.py",
                "prompt.py",
                "context.py",
                "state.py",
            }.issubset({path.name for path in package_dir.iterdir()})
        )

    def test_report_supports_single_and_multi_temporal_tasks(self) -> None:
        evidence = SatelliteEvidence(
            asset_id="scene-001",
            source="catalog-a",
            evidence="工具返回该影像覆盖目标区域。",
        )
        for task_type in ("catalog_search", "single_temporal", "multi_temporal"):
            with self.subTest(task_type=task_type):
                report = SatelliteAgentReport(
                    task_type=task_type,
                    summary="完成有界分析。",
                    evidence=[evidence],
                )
                self.assertEqual(report.task_type, task_type)

    def test_prompt_routes_temporal_modes_to_tools(self) -> None:
        prompt = build_prompt(SatelliteAgentContext())
        self.assertIn("单时相解译和多时相变化分析", prompt)
        self.assertIn("根据任务选择合适的工具组合", prompt)
        self.assertIn("多个数据源", prompt)
        self.assertIn("不生成不存在的影像", prompt)

    def test_agent_is_internal_and_registered_once_with_leader(self) -> None:
        subagent_ids = {item["id"] for item in agent_manager.list_subagents()}
        public_ids = {
            item["id"] for item in agent_manager.list_top_level_agents()
        }
        leader_source = inspect.getsource(LeaderAgent._create_middlewares)

        self.assertIn("SatelliteAgent", subagent_ids)
        self.assertNotIn("SatelliteAgent", public_ids)
        self.assertEqual(leader_source.count("SatelliteAgent()"), 1)
        self.assertNotIn("SatelliteCatalogAgent", leader_source)
        self.assertNotIn("SatelliteAnalysisAgent", leader_source)
        self.assertNotIn("SatelliteChangeAgent", leader_source)


if __name__ == "__main__":
    unittest.main()
