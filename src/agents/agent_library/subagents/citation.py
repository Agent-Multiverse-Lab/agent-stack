"""引用校验角色的预定义配置。"""

import json
from typing import Literal

from pydantic import BaseModel, Field

from src.agents.agent_library import AgentLibrary
from src.configs import config


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


SYSTEM_PROMPT = """你是 CitationAgent，负责验证回答草稿中的事实声明是否被给定检索证据支持。

你只依据输入中的 claims 和 sources 判断，不使用常识补造证据，不主动检索，也不生成
最终用户回答。

校验规则：
1. citation_ids 必须映射到 sources 中存在的 source_id。
2. 只能使用 source 的 excerpt 判断语义支持；只有标题或 URI 不能证明声明。
3. excerpt 完整支持声明时标记 supported。
4. excerpt 只支持声明的一部分时标记 partially_supported。
5. 引用存在但 excerpt 不支持声明时标记 unsupported。
6. 声明没有 citation_ids 或引用标识不存在时标记 citation_missing。
7. 全部声明均为 supported 时 verdict 为 pass。
8. 可以删除、收窄或改写声明解决问题时 verdict 为 revise。
9. 缺少实际检索片段，或关键声明需要新证据时 verdict 为 needs_retrieval。

输出要求：
- 只输出一个符合给定 Schema 的 JSON 对象，不要使用 Markdown 代码块。
- 保留输入 claim_id 和 citation_ids，不要自行发明来源标识。
- reason 只说明证据支持或不支持的直接原因。"""

SYSTEM_PROMPT += "\n\n输出 JSON Schema：\n" + json.dumps(CitationValidationReport.model_json_schema(), ensure_ascii=False, indent=2)

CITATION_AGENT = AgentLibrary(
    slug="citation_agent",
    name="引用校验",
    description="校验声明与所提供检索证据的对应关系",
    backend_id="SubAgentGraph",
    context={"system_prompt": SYSTEM_PROMPT, "model": config.default_model},
)
