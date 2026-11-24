"""基于 LangChain 官方三家协议包构造单次 Chat 运行实例，不读取数据库或环境变量。"""

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from ..utils import ModelProtocol

SUPPORTED_CHAT_PROTOCOLS = frozenset({"openai_compatible", "anthropic", "gemini"})


def supports_chat_protocol(protocol: str) -> bool:
    return protocol in SUPPORTED_CHAT_PROTOCOLS


def build_chat_model(
    *,
    protocol: ModelProtocol,
    model_id: str,
    api_key: str,
    base_url: str,
    extra_headers: dict[str, str] | None = None,
) -> BaseChatModel:
    """按协议构造 LangChain ChatModel 实例。"""
    headers = dict(extra_headers or {})
    if protocol == "openai_compatible":
        return ChatOpenAI(
            model=model_id,
            api_key=api_key,
            base_url=base_url,
            default_headers=headers,
        )
    if protocol == "anthropic":
        return ChatAnthropic(
            model=model_id,
            api_key=api_key,
            base_url=base_url,
            default_headers=headers,
        )
    if protocol == "gemini":
        return ChatGoogleGenerativeAI(
            model=model_id,
            api_key=api_key,
            base_url=base_url,
            additional_headers=headers,
        )
    raise ValueError(f"不支持的模型协议：{protocol}")


__all__ = [
    "SUPPORTED_CHAT_PROTOCOLS",
    "build_chat_model",
    "supports_chat_protocol",
]
