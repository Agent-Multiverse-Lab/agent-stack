"""Project 管理接口契约。"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints, field_validator

ProjectName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class ProjectRequest(BaseModel):
    name: ProjectName


class ProjectUpdateRequest(BaseModel):
    name: ProjectName | None = None
    pinned: bool | None = None

    @field_validator("name", "pinned")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("更新字段不能为 null")
        return value


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    pinned: bool
    pinned_at: datetime | None
    created_at: datetime
    updated_at: datetime
