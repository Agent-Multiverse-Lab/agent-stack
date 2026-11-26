"""模型管理 HTTP 请求与响应 Schema。"""

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from src.model.utils import ChatCapability, ModelCategory, ModelProtocol

T = TypeVar("T")


class ModelProvider(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str = ""
    name: str = ""
    protocol: ModelProtocol = "openai_compatible"
    base_url: str = ""
    embedding_base_url: str = ""
    rerank_base_url: str = ""
    api_key: str | None = Field(default=None, exclude=True)
    is_enabled: bool = Field(default=False, strict=True)
    has_api_key: bool = False
    models: list[dict[str, Any]] = Field(default_factory=list)


class ModelCatalogItem(BaseModel):
    model_id: str
    category: ModelCategory
    capabilities: list[ChatCapability] = Field(default_factory=list)


class ProviderModelCatalog(BaseModel):
    provider_id: str
    display_name: str
    models: list[ModelCatalogItem] = Field(default_factory=list)


class ModelApiResponse(BaseModel, Generic[T]):
    status: Literal["success"] = "success"
    data: T


__all__ = [
    "ModelApiResponse",
    "ModelCatalogItem",
    "ModelProvider",
    "ProviderModelCatalog",
]
