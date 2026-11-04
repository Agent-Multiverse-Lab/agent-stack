"""知识库组织、处理设置与持久任务的 API 契约。"""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

EntryName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255, pattern=r'^[^/\\]+$')]


class KnowledgeSettings(BaseModel):
    chunker: Literal['title', 'token'] = 'title'
    title_method: Literal['hierarchy', 'group'] = 'hierarchy'
    target_level: int = Field(default=3, ge=1, le=6)
    chunk_token_size: int = Field(default=512, ge=32, le=8192)
    embedding_model_spec: str | None = None
    top_k: int = Field(default=8, ge=1, le=50)
    candidate_limit: int = Field(default=50, ge=1, le=100)
    min_score: float | None = Field(default=None, ge=-1, le=1)
    rerank: bool = True


class KnowledgeBaseUpdate(BaseModel):
    name: EntryName
    description: str = Field(default='', max_length=10000)
    settings: KnowledgeSettings


class KnowledgeFolderCreate(BaseModel):
    name: EntryName
    parent_id: str | None = None


class KnowledgeFileUpdate(BaseModel):
    name: EntryName
    folder_id: str | None = None


class KnowledgeTaskCreate(BaseModel):
    operation: Literal['parse', 'index', 'extract', 'delete']
    file_ids: list[str] = Field(min_length=1, max_length=500)

    @model_validator(mode='after')
    def unique_files(self) -> Self:
        if len(set(self.file_ids)) != len(self.file_ids):
            raise ValueError('文件不能重复')
        return self


class KnowledgeEvaluationSample(BaseModel):
    query_id: str = Field(min_length=1)
    query: str = Field(min_length=1, max_length=2000)
    split: Literal['validation', 'test'] = 'validation'
    relevant_chunk_ids: list[str] = Field(min_length=1)


class KnowledgeEvaluationCreate(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=255)
    dataset_version: str = Field(default='1', min_length=1)
    corpus_version: str = Field(default='1', min_length=1)
    ks: list[int] = Field(default_factory=lambda: [3, 5, 8], min_length=1, max_length=10)
    samples: list[KnowledgeEvaluationSample] = Field(min_length=1, max_length=200)
