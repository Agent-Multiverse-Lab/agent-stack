from __future__ import annotations

import inspect
import unittest
from pathlib import Path

from pydantic import ValidationError

from src.agents.leaderagent.agent import LeaderAgent
from src.agents.manager import agent_manager
from src.agents.subagents.citationagent.context import CitationAgentContext
from src.agents.subagents.citationagent.prompt import build_prompt
from src.agents.subagents.citationagent.state import (
    CitationValidationItem,
    CitationValidationReport,
)


class CitationAgentContractTest(unittest.TestCase):
    """验证 CitationAgent 的包结构、契约和运行注册。"""

    def test_package_uses_standard_subagent_structure(self) -> None:
        """CitationAgent 包包含五个规定文件。"""

        package_dir = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "agents"
            / "subagents"
            / "citationagent"
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

    def test_validation_report_rejects_unknown_status(self) -> None:
        """校验报告只接受约定的 verdict 和声明状态。"""

        report = CitationValidationReport(
            verdict="pass",
            items=[
                CitationValidationItem(
                    claim_id="claim_001",
                    status="supported",
                    citation_ids=["source_001"],
                    reason="检索片段直接支持声明。",
                )
            ],
        )
        self.assertEqual(report.items[0].status, "supported")

        with self.assertRaises(ValidationError):
            CitationValidationItem(
                claim_id="claim_001",
                status="unknown",  # type: ignore[arg-type]
                reason="invalid",
            )

    def test_prompt_requires_evidence_only_json_report(self) -> None:
        """Prompt 要求只依据检索片段并输出 JSON 报告。"""

        prompt = build_prompt(CitationAgentContext())
        self.assertIn("只能使用 source 的 excerpt", prompt)
        self.assertIn("只输出一个符合给定 Schema 的 JSON 对象", prompt)
        self.assertIn("needs_retrieval", prompt)

    def test_agent_is_internal_and_registered_with_leader(self) -> None:
        """CitationAgent 是内部 Agent，并被 LeaderAgent 显式注册。"""

        subagent_ids = {
            item["id"] for item in agent_manager.list_subagents()
        }
        public_ids = {
            item["id"] for item in agent_manager.list_top_level_agents()
        }
        self.assertIn("CitationAgent", subagent_ids)
        self.assertNotIn("CitationAgent", public_ids)
        self.assertIn(
            "CitationAgent()",
            inspect.getsource(LeaderAgent._create_middlewares),
        )


if __name__ == "__main__":
    unittest.main()
