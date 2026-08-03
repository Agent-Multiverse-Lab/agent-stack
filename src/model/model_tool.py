"""根据统一 Provider 配置构造 LangChain 模型。"""

from langchain_core.embeddings import Embeddings
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from src.configs import (
    DEFAULT_BASE_MODEL_PROVIER,
    DEFAULT_EMBEDDING_MODEL_PROVIDER,
    DEFAULT_RERANK_MODEL_PROVIDER,
)
from src.configs import config as sys_config
from src.configs.model import EmbeddingModelProvider, RerankModelProvider

from .reranker import BaseReranker, DashScopeReranker


def load_model(model: str):
    """按 provider/model 规格创建聊天模型。"""
    provider, model_name = model.split("/")
    provider_info = DEFAULT_BASE_MODEL_PROVIER.get(provider)
    if not provider_info:
        raise ValueError(f"未知模型提供商: {provider}")

    base_url = provider_info.base_url
    api_key_name = provider_info.api_key.lower()
    api_key = getattr(sys_config, api_key_name, None)

    if provider in ["dashscope", "openai"]:
        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
        )
    if provider == "deepseek":
        return ChatDeepSeek(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
        )
    raise ValueError(f"不支持的模型提供商: {provider}")


def resolve_embedding_model(
    model: str | None = None,
) -> tuple[str, str, EmbeddingModelProvider]:
    """解析 Embedding 模型规格并返回对应 Provider。"""
    configured_model = (model or sys_config.embed_model).strip()
    if not configured_model or "/" not in configured_model:
        raise ValueError(
            "未配置 Embedding 模型，应设置 EMBED_MODEL=provider/model"
        )

    provider_name, model_name = configured_model.split("/", 1)
    provider = DEFAULT_EMBEDDING_MODEL_PROVIDER.get(provider_name)
    if provider is None:
        raise ValueError(f"未知 Embedding 模型提供商：{provider_name}")
    if not model_name:
        raise ValueError("Embedding 模型名称不能为空")

    return configured_model, model_name, provider


def load_embedding_model(model: str | None = None) -> Embeddings:
    """从统一 Provider 配置创建 LangChain Embedding 模型。"""
    _, model_name, provider = resolve_embedding_model(model)
    api_key = getattr(sys_config, provider.api_key.lower(), "")
    if not api_key:
        raise ValueError(f"未配置 Embedding API 密钥：{provider.api_key}")

    return OpenAIEmbeddings(
        model=model_name,
        api_key=api_key,
        base_url=provider.base_url,
        chunk_size=provider.batch_size,
        max_retries=provider.max_retries,
        request_timeout=provider.request_timeout,
    )


def resolve_rerank_model(
    model: str | None = None,
) -> tuple[str, str, RerankModelProvider]:
    """解析 Rerank 模型规格并返回对应 Provider。"""
    configured_model = (model or sys_config.rerank_model).strip()
    if not configured_model or "/" not in configured_model:
        raise ValueError(
            "未配置 Rerank 模型，应设置 RERANK_MODEL=provider/model"
        )

    provider_name, model_name = configured_model.split("/", 1)
    provider = DEFAULT_RERANK_MODEL_PROVIDER.get(provider_name)
    if provider is None:
        raise ValueError(f"未知 Rerank 模型提供商：{provider_name}")
    if not model_name:
        raise ValueError("Rerank 模型名称不能为空")

    return configured_model, model_name, provider


def load_reranker(model: str | None = None) -> BaseReranker:
    """从统一 Provider 配置创建 Reranker。"""
    _, model_name, provider = resolve_rerank_model(model)
    api_key = getattr(sys_config, provider.api_key.lower(), "")
    endpoint = getattr(sys_config, provider.endpoint.lower(), "")
    if not api_key:
        raise ValueError(f"未配置 Rerank API 密钥：{provider.api_key}")
    if not endpoint:
        raise ValueError(f"未配置 Rerank URL：{provider.endpoint}")

    if provider.name == "dashscope":
        return DashScopeReranker(
            model=model_name,
            api_key=api_key,
            endpoint=endpoint,
            request_timeout=sys_config.rerank_request_timeout_seconds,
        )
    raise ValueError(f"不支持的 Rerank 模型提供商：{provider.name}")
