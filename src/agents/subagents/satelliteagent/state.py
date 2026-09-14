from typing import Literal, NotRequired

from langchain.agents import AgentState
from pydantic import BaseModel, Field


class SatelliteEvidence(BaseModel):
    """一条可追溯的卫星数据证据。"""

    asset_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    captured_at: str = Field(default="")
    region: str = Field(default="")
    evidence: str = Field(min_length=1)


class SatelliteAgentReport(BaseModel):
    """卫星数据检索与分析结果。"""

    task_type: Literal[
        "catalog_search",
        "single_temporal",
        "multi_temporal",
        "mixed",
    ]
    summary: str = Field(min_length=1)
    evidence: list[SatelliteEvidence] = Field(default_factory=list)
    tool_facts: list[str] = Field(default_factory=list)
    missing_constraints: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class SatelliteAgentState(AgentState[SatelliteAgentReport]):
    """卫星数据 Agent 的图状态。"""

    task_type: NotRequired[str]
    asset_ids: NotRequired[list[str]]
    area_of_interest: NotRequired[str]
    time_range: NotRequired[str]
