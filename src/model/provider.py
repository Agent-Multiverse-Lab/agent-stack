"""Chat Provider 领域值类型与 Service 写入命令。"""

import json
import re
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    SecretStr,
    field_validator,
    model_validator,
)

ModelType = Literal[
    "deepseek",
    "qwen",
    "glm",
    "minomax",
    "gemini",
    "chatgpt",
    "ollama",
    "vllm",
]
ModelProtocol = Literal["openai_compatible"]
ChatCapability = Literal[
    "chat",
    "vision",
    "reasoning",
    "tools",
    "code",
    "audio",
    "video",
]
ProviderId = Annotated[
    str,
    Field(pattern=r"^[a-z0-9_-]+$", min_length=1, max_length=64),
]


def validate_model_id(value: str) -> str:
    if value != value.strip() or any(
        ord(char) < 32 or ord(char) == 127 for char in value
    ):
        raise ValueError("模型 ID 不得包含首尾空白或控制字符")
    return value


def validate_capabilities(
    value: list[ChatCapability],
) -> list[ChatCapability]:
    if len(value) != len(set(value)):
        raise ValueError("模型能力不得重复")
    return value


def normalize_base_url(value: str) -> str:
    try:
        url = urlsplit(value)
        valid = (
            url.scheme in {"http", "https"}
            and url.hostname
            and not url.username
            and not url.password
            and not url.query
            and not url.fragment
            and "?" not in value
            and "#" not in value
            and "@" not in url.netloc
            and not any(char.isspace() or ord(char) < 32 for char in value)
        )
        url.port
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(
            "base_url 必须是无用户信息、查询参数及 fragment 的 HTTP(S) 地址"
        )
    return value.rstrip("/")


def validate_api_key(value: SecretStr) -> SecretStr:
    key = value.get_secret_value()
    if (
        not key.isascii()
        or any(ord(char) < 32 or ord(char) == 127 for char in key)
        or key != key.strip()
    ):
        raise ValueError("API Key 包含无效字符")
    return value


class EnabledModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        hide_input_in_errors=True,
    )

    model_id: str = Field(min_length=1)
    model_type: ModelType
    body_overrides: dict[str, JsonValue] = Field(default_factory=dict)
    capabilities: list[ChatCapability] = Field(default_factory=list)

    _model_id_validator = field_validator("model_id")(validate_model_id)
    _capability_validator = field_validator("capabilities")(
        validate_capabilities
    )

    @field_validator("body_overrides")
    @classmethod
    def validate_overrides(
        cls,
        value: dict[str, JsonValue],
    ) -> dict[str, JsonValue]:
        reserved = {
            "model",
            "messages",
            "stream",
            "input",
            "query",
            "documents",
            "api_key",
            "base_url",
            "headers",
            "extra_headers",
            "extra_body",
        }
        if reserved.intersection(key.lower() for key in value):
            raise ValueError("请求体覆盖包含受保护字段")
        try:
            json.dumps(value, allow_nan=False)
        except (TypeError, ValueError):
            raise ValueError("请求体覆盖必须是有限的 JSON 数据") from None
        return value


class ProviderSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    name: str = Field(min_length=1, max_length=255)
    base_url: str
    protocol: ModelProtocol = "openai_compatible"
    extra_headers: dict[str, SecretStr] = Field(
        default_factory=dict,
        repr=False,
    )
    is_enabled: bool = Field(default=False, strict=True)
    enabled_models: list[EnabledModel] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("供应商名称不能为空")
        return value.strip()

    _url_validator = field_validator("base_url")(normalize_base_url)

    @field_validator("extra_headers")
    @classmethod
    def validate_headers(
        cls,
        headers: dict[str, SecretStr],
    ) -> dict[str, SecretStr]:
        seen: set[str] = set()
        for name, secret in headers.items():
            normalized = name.lower()
            value = secret.get_secret_value()
            if (
                not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name)
                or normalized in seen | {"host", "content-length", "authorization"}
                or not value.isascii()
                or any(ord(char) < 32 or ord(char) == 127 for char in value)
                or value != value.strip()
            ):
                raise ValueError("额外请求头无效或包含受保护字段")
            seen.add(normalized)
        return headers

    @model_validator(mode="after")
    def validate_unique_models(self):
        ids = [model.model_id for model in self.enabled_models]
        if len(ids) != len(set(ids)):
            raise ValueError("同一供应商内模型 ID 不得重复")
        return self


class ModelProviderCreate(ProviderSettings):
    provider_id: ProviderId
    api_key: SecretStr = Field(default=SecretStr(""), repr=False)

    _key_validator = field_validator("api_key")(validate_api_key)


class ModelProviderUpdate(ProviderSettings):
    """完整替换设置；仅省略 api_key 时保留旧密钥。"""

    api_key: SecretStr | None = Field(default=None, repr=False)

    @field_validator("api_key")
    @classmethod
    def validate_optional_api_key(
        cls,
        value: SecretStr | None,
    ) -> SecretStr:
        if value is None:
            raise ValueError("清除 API Key 请使用空字符串")
        return validate_api_key(value)


class ModelSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    provider_id: str
    provider_name: str
    model_id: str
    model_type: ModelType


__all__ = [
    "ChatCapability",
    "EnabledModel",
    "ModelProtocol",
    "ModelProviderCreate",
    "ModelProviderUpdate",
    "ModelSummary",
    "ModelType",
    "ProviderId",
    "ProviderSettings",
    "normalize_base_url",
    "validate_api_key",
    "validate_capabilities",
    "validate_model_id",
]
