"""统一模型构造入口。"""

from .model_tool import (
    load_embedding_model,
    load_model,
    resolve_embedding_model,
)

__all__ = [
    "load_embedding_model",
    "load_model",
    "resolve_embedding_model",
]
