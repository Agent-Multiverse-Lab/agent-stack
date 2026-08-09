"""附件 Library Router 使用的请求与响应实体。"""

from datetime import datetime

from pydantic import BaseModel, Field


class LibraryAttachmentItem(BaseModel):
    """附件页面中的一个文件。"""

    file_id: str
    file_name: str
    suffix: str
    content_type: str
    file_size: int
    category: str
    access_url: str
    created_at: datetime
    updated_at: datetime


class LibraryAttachmentListResponse(BaseModel):
    """附件列表的一页数据。"""

    items: list[LibraryAttachmentItem]
    next_before_id: int | None


class LibraryAttachmentRenameRequest(BaseModel):
    """修改附件展示文件名。"""

    file_name: str = Field(min_length=1, max_length=255)
