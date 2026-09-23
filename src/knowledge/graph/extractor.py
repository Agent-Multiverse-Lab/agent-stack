"""知识图谱实体关系抽取。"""

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.configs import config as sys_config
from src.model import load_model
from src.utils import logger

_SYSTEM_PROMPT = (
    "你是知识图谱抽取助手。请从给定文档中抽取关键实体"
    "（人物、组织、产品、技术、地点、事件等）以及实体间的关系。"
    "每个实体必须包含名称(name)、类型(type)和简短描述(description)。"
    "关系使用 source 和 target 引用实体名称，type 描述关系类型"
    "（如：任职于、属于、研发、合作、位于、发布、投资）。"
    "优先抽取文档核心概念，不要抽取无关紧要的实体。"
)


class GraphEntity(BaseModel):
    """抽取出的命名实体。"""

    name: str = Field(min_length=1, max_length=512)
    type: str = Field(default="", max_length=64)
    description: str = Field(default="", max_length=2000)


class GraphRelation(BaseModel):
    """实体之间的命名关系（端点引用实体名称）。"""

    source: str = Field(min_length=1, max_length=512)
    target: str = Field(min_length=1, max_length=512)
    type: str = Field(default="", max_length=128)


class GraphExtractionResult(BaseModel):
    """单次抽取的实体与关系集合。"""

    entities: list[GraphEntity] = Field(default_factory=list)
    relations: list[GraphRelation] = Field(default_factory=list)


class GraphExtractor:
    """使用快速模型从文档中抽取实体与关系。"""

    def __init__(self, model: Any | None = None) -> None:
        self._model = model or load_model(sys_config.flash_model)

    async def extract(self, markdown: str) -> GraphExtractionResult:
        """优先结构化输出，失败时回退 JSON 文本解析。"""
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=markdown),
        ]
        try:
            structured = self._model.with_structured_output(
                GraphExtractionResult
            )
            return await structured.ainvoke(messages)
        except Exception:
            logger.exception("图谱结构化输出失败，回退 JSON 文本解析")
            result = await self._model.ainvoke(
                [
                    SystemMessage(content=_SYSTEM_PROMPT + " 只输出 JSON。"),
                    HumanMessage(content=markdown),
                ]
            )
            return self._parse_json_result(result.text)

    @staticmethod
    def _parse_json_result(text: str) -> GraphExtractionResult:
        """解析模型返回的 JSON 文本，容忍 markdown 代码块包裹。"""
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = stripped.removeprefix("```")
            stripped = stripped.removeprefix("json\n")
            stripped = stripped.removesuffix("```")
        value = json.loads(stripped)
        if isinstance(value, list):
            value = {"entities": value}
        return GraphExtractionResult.model_validate(value)
