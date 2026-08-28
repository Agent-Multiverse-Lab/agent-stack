"""Thread 接口的请求与响应 Schema。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ThreadRequest(BaseModel):
    """创建顶层对话的请求。"""

    title: str | None = None
    summary: str | None = None
    agent_id: str
    metadata: dict[str, Any] | None = None


class ThreadResponse(BaseModel):
    """创建成功后的对话信息。"""

    uid: str
    title: str
    thread_id: str
    agent_id: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ThreadSummaryResponse(BaseModel):
    """对话列表与详情共用的基础信息。"""

    thread_id: str
    title: str
    summary: str | None
    agent_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None


class ThreadRunMetadataResponse(BaseModel):
    """一条消息对应的 Agent Run 元数据。"""

    run_id: str
    run_type: str
    status: str
    parent_run_id: str | None
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None
    finished_at: datetime | None


# FIXEME: Thread 刷新只公开 ask_user 所需字段，不暴露 checkpoint。
class InteractionRequired(BaseModel):
    """等待当前用户回答的 ask_user 问题。"""

    kind: str
    parent_run_id: str
    question: str
    options: list[str]


class ThreadMessageAttachmentResponse(BaseModel):
    """历史消息引用的附件。"""

    file_id: str
    file_name: str
    content_type: str
    file_size: int
    available: bool
    access_url: str | None


class ThreadMessageResponse(BaseModel):
    """指定对话中的持久化消息。"""

    message_id: int
    role: str
    content: str
    image_content: str | None
    message_type: str
    status: str
    request_id: str | None
    run: ThreadRunMetadataResponse | None
    attachments: list[ThreadMessageAttachmentResponse] = Field(
        default_factory=list
    )
    created_at: datetime
    updated_at: datetime


class ThreadListResponse(BaseModel):
    """对话列表游标页。"""

    items: list[ThreadSummaryResponse]
    next_cursor: str | None


class ThreadDetailResponse(BaseModel):
    """对话及其一页消息历史。"""

    thread: ThreadSummaryResponse
    messages: list[ThreadMessageResponse]
    next_before_message_id: int | None
    # FIXEME: Resume Run 没有触发消息，Thread 状态必须独立于消息列表返回。
    active_run: ThreadRunMetadataResponse | None
    pending_interaction: InteractionRequired | None


class ThreadUpdateRequest(BaseModel):
    """更新当前用户拥有的对话。"""

    title: str | None = Field(default=None, max_length=255)
    summary: str | None = None
    metadata: dict[str, Any] | None = None


class UploadedAttachmentResponse(BaseModel):
    """上传成功的用户附件。"""

    file_id: str
    file_name: str
    content_type: str
    file_size: int
    bucket_name: str
    object_name: str
    access_url: str
