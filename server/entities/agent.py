"""Agent 接口的请求与响应 Schema。"""

from typing import Any

from pydantic import BaseModel, Field


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
    image_content: str | None = Field(None, description="图像文件")
    is_resume: Any | None = Field(None, description="resume选项，用于特殊如Hil")
    parent_run_id: str | None = Field(None, description="父事件id,没有就自己的id")


class AgentSummary(BaseModel):
    """公开顶层 Agent 的摘要。"""

    id: str
    name: str
    description: str
