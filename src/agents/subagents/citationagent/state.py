from typing import Literal, NotRequired

from langchain.agents import AgentState
from pydantic import BaseModel, Field


class CitationSource(BaseModel):
    """一次校验可使用的检索证据。"""

    source_id: str = Field(min_length=1, description="稳定的来源标识")
    title: str = Field(default="", description="来源标题")
    uri: str = Field(default="", description="URL 或知识文件标识")
    excerpt: str = Field(default="", description="实际检索片段")


class CitationClaim(BaseModel):
    """待验证的事实声明及其候选引用。"""

    claim_id: str = Field(min_length=1, description="稳定的声明标识")
    text: str = Field(min_length=1, description="待验证声明")
    citation_ids: list[str] = Field(
        default_factory=list,
        description="声明引用的 source_id",
    )


class CitationValidationItem(BaseModel):
    """单条声明的引用校验结果。"""

    claim_id: str = Field(min_length=1)
    status: Literal[
        "supported",
        "partially_supported",
        "unsupported",
        "citation_missing",
    ]
    citation_ids: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)


class CitationValidationReport(BaseModel):
    """CitationAgent 返回给 LeaderAgent 的校验报告。"""

    verdict: Literal["pass", "revise", "needs_retrieval"]
    items: list[CitationValidationItem] = Field(default_factory=list)


class CitationAgentState(AgentState[CitationValidationReport]):
    """CitationAgent 的图状态。"""

    draft: NotRequired[str]
    claims: NotRequired[list[CitationClaim]]
    sources: NotRequired[list[CitationSource]]
