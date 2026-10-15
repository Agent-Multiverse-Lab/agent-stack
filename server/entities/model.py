"""模型管理 HTTP 请求与响应 DTO。"""

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from src.model.provider import (
    ChatCapability,
    EnabledModel,
    ModelProtocol,
    normalize_base_url,
    validate_api_key,
    validate_capabilities,
    validate_model_id,
)


class ChatModelItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    name: str
    display_name: str
    version: str
    provider: str
    icon: str
    is_available: bool
    is_default: bool
    is_fallback: bool
    is_flash: bool


class ChatModelListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    default_model: str
    fallback_model: str
    flash_model: str
    image_model: str
    models: list[ChatModelItem]


class ModelProviderSummary(BaseModel):
    provider_id: str
    name: str
    is_enabled: bool
    has_api_key: bool


class ModelProviderResponse(ModelProviderSummary):
    base_url: str
    protocol: ModelProtocol
    enabled_models: list[EnabledModel]


class ProviderWriteResult(BaseModel):
    provider_id: str
    cache_refreshed: bool


class ConnectionTestResult(BaseModel):
    success: bool
    elapsed_ms: float
    error: str | None = None
    status_code: int | None = None


class SettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(min_length=1)
    capabilities: list[ChatCapability] = Field(default_factory=list)

    _id_validator = field_validator("model_id")(validate_model_id)
    _capability_validator = field_validator("capabilities")(
        validate_capabilities
    )


class ModelSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    base_url: str
    api_key: SecretStr | None = Field(default=None, repr=False)
    is_enabled: bool = Field(default=False, strict=True)
    models: list[SettingsModel] = Field(default_factory=list)

    _url_validator = field_validator("base_url")(normalize_base_url)

    @field_validator("api_key")
    @classmethod
    def validate_key(cls, value: SecretStr | None) -> SecretStr:
        if value is None:
            raise ValueError("API Key 不可为 null")
        return validate_api_key(value)


__all__ = [
    "ChatModelItem",
    "ChatModelListResponse",
    "ConnectionTestResult",
    "ModelProviderResponse",
    "ModelProviderSummary",
    "ModelSettingsRequest",
    "ProviderWriteResult",
    "SettingsModel",
]
