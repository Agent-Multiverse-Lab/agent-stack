"""Agent 接口的请求与响应 Schema。"""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class AgentCreateRequest(BaseModel):
    """创建自定义 Agent 的预留请求。"""


class AgentRunCreateRequest(BaseModel):
    """创建 Agent Run 的请求。"""

    query: str | None = Field(default=None, description="问题")
    agent_id: str = Field(default=..., description="agent的name")
    thread_id: str = Field(default=..., description="对话thraed_id")
    thread_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="单次 Agent Run 元数据",
    )
    msg_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="单次输入消息元数据",
    )
    image_content: str | None = Field(None, description="图像文件")


class AgentRunResumeRequest(BaseModel):
    """从被打断 Run 创建恢复请求。"""

    thread_id: str = Field(default=..., description="对话 thread_id")
    thread_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Resume Run 元数据",
    )

    # 问题及选项的业务校验由 Resume Service 按父 Run 完成。
    @field_validator("thread_metadata")
    @classmethod
    def validate_resume_metadata(
        cls,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = dict(metadata)
        resume = normalized.get("resume")
        if not isinstance(resume, dict):
            raise ValueError("thread_metadata.resume 必须是对象")
        answers = resume.get("answers")
        if not isinstance(answers, dict) or not answers or not all(
            isinstance(key, str) and key and isinstance(value, str)
            for key, value in answers.items()
        ):
            raise ValueError("thread_metadata.resume.answers 必须是非空回答字典")
        normalized["resume"] = {"answers": answers}
        return normalized


class AgentSummary(BaseModel):
    """公开顶层 Agent 的摘要。"""

    id: str
    name: str
    description: str
