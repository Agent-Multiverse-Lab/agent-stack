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
