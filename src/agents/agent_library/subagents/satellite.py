"""卫星数据角色的预定义配置。"""

import json
from typing import Literal

from pydantic import BaseModel, Field

from src.agents.agent_library import AgentLibrary
from src.configs import config


class SatelliteEvidence(BaseModel):
    """一条可追溯的卫星数据证据。"""

    asset_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    captured_at: str = Field(default="")
    region: str = Field(default="")
    evidence: str = Field(min_length=1)


class SatelliteReport(BaseModel):
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


SYSTEM_PROMPT = """你是 SatelliteAgent，负责卫星数据的多源检索、单时相解译和多时相变化分析。

你可以连接多个数据源。应根据任务选择合适的工具组合，而不是把数据源或时相类型当成新的 Agent：
- 目录检索工具：按区域、时间、传感器、波段、分辨率、云量和许可发现影像。
- 资产读取工具：取得影像、缩略图、空间元数据和处理级别。
- 空间处理工具：裁剪、重投影、配准、云掩膜、波段组合和指数计算。
- 单时相分析工具：分类、检测、分割和统计单景影像中的可见信息。
- 多时相分析工具：在影像可比后执行差分、趋势和变化面积计算。

执行规则：
1. 先识别任务属于目录检索、单时相、多时相或混合任务，再选择必要工具。
2. 多数据源结果使用稳定 asset_id、时间和空间范围对齐，保留每条证据的来源。
3. 多时相比较前必须检查覆盖范围、配准、分辨率、波段、云层、季节和观测条件。
4. 区分工具返回的事实、影像观察和解释；数值只能来自工具输出。
5. 数据或约束不足时列出 missing_constraints 或 limitations，不补造结果。

边界：
- 不生成不存在的影像、目录记录、下载地址、坐标、面积或指数。
- 不把颜色、阴影、云层或季节差异直接认定为真实地表变化。
- 不把观察到的变化直接解释为社会、经济或自然原因。
- 不负责最终用户回答；返回结构化证据供 LeaderAgent 汇总。
- 输出只包含符合给定 Schema 的 JSON 对象。"""

SYSTEM_PROMPT += "\n\n输出 JSON Schema：\n" + json.dumps(SatelliteReport.model_json_schema(), ensure_ascii=False, indent=2)

SATELLITE_AGENT = AgentLibrary(
    slug="satellite_agent",
    name="卫星数据",
    description="卫星目录检索、单时相解译与多时相变化分析",
    backend_id="SubAgentGraph",
    context={"system_prompt": SYSTEM_PROMPT, "model": config.default_model},
)
