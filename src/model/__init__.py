"""模型领域类型、预置、仓储、运行时工厂与管理服务统一出口。"""

from . import service
from .model_provider.chat import SUPPORTED_CHAT_PROTOCOLS, build_chat_model, supports_chat_protocol
from .model_provider.embedding import (
    SUPPORTED_EMBEDDING_PROTOCOLS,
    EmbeddingError,
    HttpEmbeddings,
    build_embedding_model,
)
from .model_provider.reranker import (
    BaseReranker,
    DashScopeReranker,
    HttpReranker,
    RerankDocument,
    RerankError,
    RerankResult,
    build_reranker,
)
from .presets import MODEL_PROVIDER_PRESETS, ModelProviderPreset, PresetModel
from .repository import ModelProviderRepository
from .runtime import (
    load_chat_model,
    load_embedding_model,
    load_reranker,
    validate_model,
)
from .utils import (
    ChatCapability,
    ModelCategory,
    ModelProtocol,
    ModelType,
    resolve_chat_model_selection,
    resolve_provider_api_key,
)

__all__ = [
    "BaseReranker",
    "ChatCapability",
    "DashScopeReranker",
    "EmbeddingError",
    "HttpEmbeddings",
    "HttpReranker",
    "MODEL_PROVIDER_PRESETS",
    "ModelCategory",
    "ModelProtocol",
    "ModelProviderPreset",
    "ModelProviderRepository",
    "ModelType",
    "PresetModel",
    "RerankDocument",
    "RerankError",
    "RerankResult",
    "SUPPORTED_CHAT_PROTOCOLS",
    "SUPPORTED_EMBEDDING_PROTOCOLS",
    "build_chat_model",
    "build_embedding_model",
    "build_reranker",
    "load_chat_model",
    "load_embedding_model",
    "load_reranker",
    "resolve_chat_model_selection",
    "resolve_provider_api_key",
    "service",
    "supports_chat_protocol",
    "validate_model",
]
