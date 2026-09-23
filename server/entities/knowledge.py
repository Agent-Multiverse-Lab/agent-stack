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


class KnowledgeBaseDeleteResponse(BaseModel):
    """知识库删除结果。"""

    kb_id: str
    deleted_file_count: int


class KnowledgeFileDeleteResponse(BaseModel):
    """知识文件删除结果。"""

    file_id: str


class KnowledgeFileMarkdownResponse(BaseModel):
    """知识文件解析产物。"""

    file_id: str
    markdown: str


class KnowledgeExtractResponse(BaseModel):
    """知识图谱抽取结果。"""

    kb_id: str
    file_id: str
    status: str
    entity_count: int
    relation_count: int


class KnowledgeGraphNode(BaseModel):
    """知识图谱实体节点。"""

    entity_id: str
    name: str
    type: str
    description: str
    file_id: str


class KnowledgeGraphEdge(BaseModel):
    """知识图谱关系边。"""

    relation_id: str
    source_entity_id: str
    target_entity_id: str
    type: str


class KnowledgeGraphResponse(BaseModel):
    """知识库全量图谱。"""

    kb_id: str
    nodes: list[KnowledgeGraphNode]
    edges: list[KnowledgeGraphEdge]
    entity_count: int
    relation_count: int


class KnowledgeEntitySearchRequest(BaseModel):
    """实体向量检索请求。"""

    query: str = Field(min_length=1)
    limit: int = Field(default=20, ge=1, le=100)


class KnowledgeEntitySearchHit(BaseModel):
    """实体检索命中。"""

    entity_id: str
    name: str
    type: str
    description: str
    file_id: str
    similarity: float


class KnowledgeEntitySearchResponse(BaseModel):
    """实体向量检索结果。"""

    kb_id: str
    hits: list[KnowledgeEntitySearchHit]


class KnowledgeChatRequest(BaseModel):
    """知识库问答请求。"""

    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=8, ge=1, le=20)


class KnowledgeCitation(BaseModel):
    """问答引用来源。"""

    file_id: str
    file_name: str
    chunk_id: str
    excerpt: str


class KnowledgeChatResponse(BaseModel):
    """知识库问答结果。"""

    kb_id: str
    answer: str
    citations: list[KnowledgeCitation]
