"""知识库接口的请求与响应 Schema。"""

from pydantic import BaseModel, Field


class KnowledgeBaseCreateRequest(BaseModel):
    """知识库创建请求。"""

    name: str = Field(min_length=1, max_length=255)
    description: str = ""


class KnowledgeBaseResponse(BaseModel):
    """知识库基础信息。"""

    kb_id: str
    name: str
    description: str
    status: str


class KnowledgeFileResponse(BaseModel):
    """知识文件解析信息。"""

    file_id: str
    kb_id: str
    original_file_name: str
    original_object_name: str
    markdown_object_name: str | None
    content_type: str
    file_size: int
    status: str
    error_message: str | None


class KnowledgeIndexResponse(BaseModel):
    """知识文件索引结果。"""

    kb_id: str
    file_id: str
    status: str
    chunk_count: int
    collection_name: str
    embedding_model_spec: str
    embedding_dimension: int


class KnowledgeSearchRequest(BaseModel):
    """知识库检索请求。"""

    kb_id: str = Field(min_length=1, max_length=128)
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=100)


class KnowledgeDeleteRequest(BaseModel):
    """知识记录删除请求。"""

    kb_id: str = Field(min_length=1, max_length=128)
    record_ids: list[str] = Field(min_length=1)
