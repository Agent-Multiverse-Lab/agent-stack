"""Sandbox workspace API schemas."""

from pydantic import BaseModel, Field


class SandboxWorkspaceEntry(BaseModel):
    name: str
    path: str
    kind: str
    size: int | None = None
    modified_at: str = ""
    file_type: str | None = None


class SandboxWorkspaceResponse(BaseModel):
    thread_id: str
    sandbox_id: str
    status: str = "running"
    path: str
    entries: list[SandboxWorkspaceEntry] = Field(default_factory=list)


class SandboxFileContentResponse(BaseModel):
    thread_id: str
    sandbox_id: str
    path: str
    content: str
    encoding: str = "utf-8"
    truncated: bool = False


class SandboxFileRenameRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    path: str = Field(min_length=1, max_length=4096)
    name: str = Field(min_length=1, max_length=255)


class SandboxFileUpdateRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    path: str = Field(min_length=1, max_length=4096)
    content: str = Field(max_length=200_000)
    previous_content: str = Field(max_length=200_000)


class SandboxFileOperationResponse(BaseModel):
    path: str
