"""模型领域类型、预置、运行时工厂与管理服务统一出口。"""

from . import service
from .model_provider.chat import (
    SUPPORTED_CHAT_PROTOCOLS,
    build_chat_model,
    load_chat_model,
    supports_chat_protocol,
)
from .model_provider.embedding import (
    SUPPORTED_EMBEDDING_PROTOCOLS,
    EmbeddingError,
    HttpEmbeddings,
    build_embedding_model,
    load_embedding_model,
)
from .model_provider.reranker import (
    BaseReranker,
    HttpReranker,
    RerankDocument,
    RerankError,
    RerankResult,
    build_reranker,
    load_reranker,
)
from .presets import MODEL_PROVIDER_PRESETS, ModelProviderPreset, PresetModel
from .service import ResolvedModel, get_enabled_model
from .utils import (
    ChatCapability,
    ModelCategory,
    ModelProtocol,
    parse_model_ref,
    resolve_provider_api_key,
)

__all__ = [
    "BaseReranker",
    "ChatCapability",
    "EmbeddingError",
    "HttpEmbeddings",
    "HttpReranker",
    "MODEL_PROVIDER_PRESETS",
    "ModelCategory",
    "ModelProtocol",
    "ModelProviderPreset",
    "PresetModel",
    "RerankDocument",
    "RerankError",
    "RerankResult",
    "ResolvedModel",
    "SUPPORTED_CHAT_PROTOCOLS",
    "SUPPORTED_EMBEDDING_PROTOCOLS",
    "build_chat_model",
    "build_embedding_model",
    "build_reranker",
    "get_enabled_model",
    "load_chat_model",
    "load_embedding_model",
    "load_reranker",
    "parse_model_ref",
    "resolve_provider_api_key",
    "service",
    "supports_chat_protocol",
]
