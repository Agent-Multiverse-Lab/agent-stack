"""知识条目接口的响应 Schema。"""

from pydantic import BaseModel


class KnowledgeItem(BaseModel):
    """知识条目响应。"""

    id: str
    kind: str
    title: str
    summary: str
    content_text: str | None = None
    file_name: str | None = None
    path: str | None = None
    minio_url: str | None = None
    markdown_file: str | None = None
    created_at: str
    updated_at: str
