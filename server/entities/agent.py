"""Agent 接口的请求与响应 Schema。"""

from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    field_validator,
    model_validator,
)


class AgentContext(BaseModel):
    """Agent 运行上下文配置。"""

    system_prompt: str
    model: str
    summary_threshold: int
    summary_keep_messages: int
    summary_prompt: str
    summary_tool_result_token_limit: int
    tools: list[Any]
    mcps: list[str]
    skill_root: str | None


class AgentResponse(BaseModel):
    """Agent 领域实体响应。"""

    id: str
    name: str
    description: str
    is_subagent: bool
    enabled: bool
    context: AgentContext | None = None


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


class AgentUpdateRequest(BaseModel):
    """只更新数据库 Agent 的基础展示字段和启用状态。"""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)] | None = None
    description: str | None = None
    enabled: StrictBool | None = None

    @model_validator(mode="after")
    def validate_partial_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("更新字段不能为 null")
        return self
