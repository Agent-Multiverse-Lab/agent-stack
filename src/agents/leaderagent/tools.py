from typing import Annotated

from langchain_core.tools import tool
from langgraph.types import interrupt
from pydantic import BaseModel, Field


class QuestionOption(BaseModel):
    """供用户选择的答案。"""

    label: str = Field(description="用户看到的选项文字")
    value: str = Field(description="回答时使用的选项值")


class HumanQuestion(BaseModel):
    """Agent 生成的一道澄清问题。"""

    question_id: str = Field(description="本次提问内唯一的问题标识")
    question: str = Field(description="需要用户回答的具体问题")
    options: list[QuestionOption] = Field(
        min_length=1,
        max_length=3,
        description="针对该问题生成的 1～3 个明确且有区分度的可选答案，优先提供 3 个，合理选项不足时不凑数",
    )

@tool
def calculator(a: Annotated[int, "计算元素a"], b: Annotated[int, "计算元素b"]):
    """计算专用的计算器，当用户有计算需求请调用该工具"""
    return a + b


@tool
def ask_user(
    questions: Annotated[
        list[HumanQuestion],
        "本次需要用户回答的问题列表。将可一起回答的独立问题合并提交，每个问题提供 1～3 个明确选项。",
    ],
) -> dict[str, str]:
    """缺少影响任务执行的关键信息，或需要用户选择方案时，暂停并向用户提问。

    根据任务生成具体问题和清晰的选项，不询问已有上下文能确定的信息。
    每道问题最多提供 3 个选项
    将当前能一起回答的独立问题放在同一次调用中；依赖前一答案的问题留待之后询问。
    返回按 question_id 对应的用户答案，答案使用选项的 value。
    """
    return interrupt(
        {
            "kind": "ask_user",
            "questions": [question.model_dump() for question in questions],
        }
    )
