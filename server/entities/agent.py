"""Agent 接口的请求与响应 Schema。"""

from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
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
    agent_id: str = Field(default=..., description="Agent 标识")
    thread_id: str = Field(default=..., description="对话 thread_id")
    dispatch_policy: Literal["enqueue", "reject", "steer"] = "enqueue"
    request_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="请求元数据：type（chat/resume）、model、request_id、attachment_file_ids、resume.answers",
    )
    image_content: str | None = Field(None, description="图像文件")


class QueuedAgentRunResponse(BaseModel):
    """等待区 202 排队响应。"""

    run_id: None = None
    thread_id: str
    status: Literal["queued"] = "queued"
    dispatch_policy: Literal["enqueue", "reject", "steer"]
    request_id: str
    queue_position: int = 1
    steering_run_id: str | None = None
    stream_url: None = None

    @classmethod
    def from_request(
        cls,
        request: Any,
        active_run: Any | None = None,
        *,
        queue_position: int = 1,
    ) -> Self:
        return cls(
            thread_id=str(request.thread_id),
            dispatch_policy=request.dispatch_policy,
            request_id=str(request.request_id),
            queue_position=queue_position,
            steering_run_id=(
                str(active_run.id)
                if active_run is not None and request.dispatch_policy == "steer"
                else None
            ),
        )


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
