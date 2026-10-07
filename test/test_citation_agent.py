import unittest

from pydantic import ValidationError

from src.agents.agent_library.subagents.citation import CITATION_AGENT, CitationValidationItem, CitationValidationReport


class CitationAgentContractTest(unittest.TestCase):
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

        prompt = CITATION_AGENT.context["system_prompt"]
        self.assertIn("只能使用 source 的 excerpt", prompt)
        self.assertIn("只输出一个符合给定 Schema 的 JSON 对象", prompt)
        self.assertIn("needs_retrieval", prompt)
