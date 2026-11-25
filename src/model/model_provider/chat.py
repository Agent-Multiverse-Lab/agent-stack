"""基于 LangChain 官方三家协议包构造单次 Chat 运行实例。"""

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from ..repository import fetch_model_config
from ..utils import ModelProtocol, resolve_provider_api_key

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


async def load_chat_model(
    model_ref: str,
    *,
    db: AsyncSession | None = None,
) -> BaseChatModel:
    """按入库配置加载单次执行使用的 LangChain ChatModel 实例。"""
    provider, model = await fetch_model_config(model_ref, category="chat", db=db)
    return build_chat_model(
        protocol=provider.protocol,
        model_id=model["model_id"],
        api_key=resolve_provider_api_key(provider.api_key or ""),
        base_url=provider.base_url,
        extra_headers=dict(provider.extra_headers or {}),
    )


__all__ = [
    "SUPPORTED_CHAT_PROTOCOLS",
    "build_chat_model",
    "load_chat_model",
    "supports_chat_protocol",
]
