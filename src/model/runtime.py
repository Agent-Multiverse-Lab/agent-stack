"""统一运行时门面：按入库 provider/model 查库校验，分派构造 Chat / Embedding / Rerank 实例。"""

from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.configs import config as sys_config
from src.database import session_context

from .model_provider.chat import build_chat_model, supports_chat_protocol
from .model_provider.embedding import (
    SUPPORTED_EMBEDDING_PROTOCOLS,
    HttpEmbeddings,
    build_embedding_model,
)
from .model_provider.reranker import BaseReranker, build_reranker
from .repository import ModelProviderRepository
from .utils import (
    ModelCategory,
    ModelProtocol,
    ModelType,
    normalize_base_url,
    normalize_enabled_models,
    normalize_optional_url,
    resolve_provider_api_key,
    validate_extra_headers,
    validate_protocol,
)


@dataclass(frozen=True, slots=True)
class _ResolvedModel:
    """仅模块内部使用的已解析模型连接描述，不对外暴露凭据。"""

    provider_id: str
    model_id: str
    model_type: ModelType
    category: ModelCategory
    protocol: ModelProtocol
    base_url: str
    embedding_base_url: str
    rerank_base_url: str
    api_key: str
    extra_headers: dict[str, str]


async def _resolve(
    db: AsyncSession,
    model_ref: str,
    *,
    expected_category: ModelCategory | None = None,
    require_enabled: bool = True,
) -> _ResolvedModel:
    if not isinstance(model_ref, str) or model_ref != model_ref.strip():
        raise ValueError("模型引用必须为 provider_id/model_id")
    provider_id, separator, model_id = model_ref.partition("/")
    if not separator or not provider_id or not model_id:
        raise ValueError("模型引用必须为 provider_id/model_id")

    provider = await ModelProviderRepository(db).get_model_provider_by_id(provider_id)
    if provider is None:
        raise LookupError("模型供应商不存在")
    if require_enabled and not provider.is_enabled:
        raise ValueError("模型供应商已停用")

    protocol = validate_protocol(provider.protocol)
    base_url = normalize_base_url(provider.base_url)
    embedding_base_url = normalize_optional_url(getattr(provider, "embedding_base_url", "") or "")
    rerank_base_url = normalize_optional_url(getattr(provider, "rerank_base_url", "") or "")
    extra_headers = validate_extra_headers(dict(getattr(provider, "extra_headers", None) or {}))
    models = normalize_enabled_models(
        list(getattr(provider, "enabled_models", None) or []),
        require_model_type=True,
        strip_legacy=True,
    )

    model = next((item for item in models if item["model_id"] == model_id), None)
    if model is None:
        raise LookupError("模型未配置")
    category: ModelCategory = model["category"]
    if expected_category is not None and category != expected_category:
        raise ValueError(
            f"模型类型不匹配：期望 {expected_category}，实际 {category}"
        )

    if category == "chat" and not supports_chat_protocol(protocol):
        raise ValueError(f"不支持的模型协议：{protocol}")
    if category == "embedding" and protocol not in SUPPORTED_EMBEDDING_PROTOCOLS:
        raise ValueError(f"不支持的 Embedding 协议：{protocol}")

    if not rerank_base_url and model.get("endpoint"):
        rerank_base_url = normalize_base_url(model["endpoint"])

    return _ResolvedModel(
        provider_id=provider_id,
        model_id=model_id,
        model_type=model["model_type"],
        category=category,
        protocol=protocol,
        base_url=base_url,
        embedding_base_url=embedding_base_url,
        rerank_base_url=rerank_base_url,
        api_key=resolve_provider_api_key(provider.api_key or ""),
        extra_headers=extra_headers,
    )


async def _resolve_with_session(
    model_ref: str,
    *,
    expected_category: ModelCategory,
    db: AsyncSession | None = None,
) -> _ResolvedModel:
    if db is not None:
        return await _resolve(db, model_ref, expected_category=expected_category)
    async with session_context() as session:
        return await _resolve(session, model_ref, expected_category=expected_category)


async def validate_model(
    db: AsyncSession,
    model_ref: str,
    *,
    category: ModelCategory = "chat",
) -> None:
    """校验模型引用在数据库中存在、已启用且类别匹配。"""
    await _resolve(db, model_ref, expected_category=category, require_enabled=True)


async def load_chat_model(
    model_ref: str,
    *,
    db: AsyncSession | None = None,
) -> BaseChatModel:
    """按入库配置加载单次执行使用的 LangChain ChatModel 实例。"""
    spec = await _resolve_with_session(model_ref, expected_category="chat", db=db)
    return build_chat_model(
        protocol=spec.protocol,
        model_id=spec.model_id,
        api_key=spec.api_key,
        base_url=spec.base_url,
        extra_headers=spec.extra_headers,
    )


async def load_embedding_model(
    model_ref: str | None = None,
    *,
    db: AsyncSession | None = None,
) -> HttpEmbeddings:
    """按入库配置加载 HTTP Embedding 模型实例。"""
    ref = (model_ref or sys_config.embed_model).strip()
    if not ref:
        raise ValueError("未配置 Embedding 模型，应设置 EMBED_MODEL=provider/model")
    spec = await _resolve_with_session(ref, expected_category="embedding", db=db)
    return build_embedding_model(
        protocol=spec.protocol,
        model_id=spec.model_id,
        api_key=spec.api_key,
        base_url=spec.embedding_base_url or spec.base_url,
        extra_headers=spec.extra_headers,
        batch_size=sys_config.embedding_batch_size,
        request_timeout=sys_config.embedding_request_timeout_seconds,
    )


async def load_reranker(
    model_ref: str | None = None,
    *,
    db: AsyncSession | None = None,
) -> BaseReranker:
    """按入库配置加载 HTTP Rerank 模型实例。"""
    ref = (model_ref or sys_config.rerank_model).strip()
    if not ref:
        raise ValueError("未配置 Rerank 模型，应设置 RERANK_MODEL=provider/model")
    spec = await _resolve_with_session(ref, expected_category="rerank", db=db)
    endpoint = spec.rerank_base_url or None
    if endpoint is None and spec.provider_id == "dashscope" and sys_config.dashscope_rerank_url.strip():
        endpoint = sys_config.dashscope_rerank_url.strip()
    return build_reranker(
        protocol=spec.protocol,
        model_id=spec.model_id,
        api_key=spec.api_key,
        base_url=spec.base_url,
        endpoint=endpoint,
        extra_headers=spec.extra_headers,
        request_timeout=sys_config.rerank_request_timeout_seconds,
    )


__all__ = [
    "load_chat_model",
    "load_embedding_model",
    "load_reranker",
    "validate_model",
]
