"""模型管理 HTTP 请求与响应 Schema。"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.model.utils import (
    normalize_enabled_models,
    normalize_optional_url,
    validate_api_key,
)


class ModelProvider(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str = ""
    name: str = ""
    base_url: str = ""
    embedding_base_url: str = ""
    rerank_base_url: str = ""
    api_key: str | None = Field(default=None, exclude=True)
    is_enabled: bool = Field(default=False, strict=True)
    has_api_key: bool = False
    models: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("base_url", "embedding_base_url", "rerank_base_url")
    @classmethod
    def _validate_urls(cls, value: str) -> str:
        return normalize_optional_url(value)

    @field_validator("api_key")
    @classmethod
    def _validate_api_key(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("API Key 不可为 null")
        return validate_api_key(value)

    @field_validator("models")
    @classmethod
    def _validate_models(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for item in value:
            if not isinstance(item, dict):
                raise ValueError("模型配置项必须是字典")
            unknown = set(item.keys()) - {"model_id", "category", "capabilities"}
            if unknown:
                raise ValueError(f"模型配置包含未知字段：{sorted(unknown)}")
        return normalize_enabled_models(value)


__all__ = ["ModelProvider"]
