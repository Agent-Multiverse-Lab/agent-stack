"""由已解析 Provider 连接构造单次 Chat 运行对象。"""

from copy import deepcopy

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, Field, JsonValue, SecretStr

from .provider import ModelProtocol, ModelType

SUPPORTED_CHAT_PROTOCOLS = frozenset({"openai_compatible"})


class ModelConnection(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    provider_id: str
    model_id: str
    model_type: ModelType
    protocol: ModelProtocol
    base_url: str
    api_key: SecretStr = Field(repr=False)
    extra_headers: dict[str, SecretStr] = Field(repr=False)
    body_overrides: dict[str, JsonValue]

    def request_headers(self) -> dict[str, str]:
        """仅在实际请求边界解封凭据。"""
        headers = {
            name: value.get_secret_value()
            for name, value in self.extra_headers.items()
        }
        if key := self.api_key.get_secret_value():
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def provider_headers(self) -> dict[str, str]:
        """返回不含 Authorization 的供应商私有请求头。"""
        return {
            name: value.get_secret_value()
            for name, value in self.extra_headers.items()
        }


def supports_chat_protocol(protocol: str) -> bool:
    return protocol in SUPPORTED_CHAT_PROTOCOLS


def create_chat_model(connection: ModelConnection) -> BaseChatModel:
    """按协议构造 ChatModel，不读取数据库、缓存或环境变量。"""
    if connection.protocol != "openai_compatible":
        raise ValueError(f"不支持的模型协议：{connection.protocol}")
    return ChatOpenAI(
        model=connection.model_id,
        api_key=connection.api_key.get_secret_value(),
        base_url=connection.base_url,
        default_headers=connection.provider_headers(),
        extra_body=deepcopy(connection.body_overrides),
    )


__all__ = [
    "ModelConnection",
    "SUPPORTED_CHAT_PROTOCOLS",
    "create_chat_model",
    "supports_chat_protocol",
]
