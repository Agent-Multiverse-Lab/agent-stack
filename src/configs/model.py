from pydantic import BaseModel, Field


class EmbeddingModelProvider(BaseModel):
    """定义 Embedding 模型提供商的连接配置。"""

    name: str = Field(..., description="模型提供商名称")
    api_key: str = Field(..., description="API 密钥配置字段")
    base_url: str = Field(..., description="OpenAI 兼容 API 地址")
    batch_size: int = Field(default=32, gt=0, description="单次向量化批大小")
    max_retries: int = Field(default=3, ge=0, description="请求最大重试次数")
    request_timeout: float = Field(
        default=30.0,
        gt=0,
        description="单次请求超时秒数",
    )
    batch_size: int = Field(default=32, gt=0, description="单次向量化批大小")
    max_retries: int = Field(default=3, ge=0, description="请求最大重试次数")
    request_timeout: float = Field(
        default=30.0,
        gt=0,
        description="单次请求超时秒数",
    )


class RerankModelProvider(BaseModel):
    """定义 Rerank 模型提供商的配置字段。"""

    name: str = Field(..., description="模型提供商名称")
    api_key: str = Field(..., description="API 密钥配置字段")
    endpoint: str = Field(..., description="Rerank URL 配置字段")


DEFAULT_EMBEDDING_MODEL_PROVIDER: dict[str, EmbeddingModelProvider] = {
    "dashscope": EmbeddingModelProvider(
        name="dashscope",
        api_key="DASHSCOPE_API_KEY",
        base_url="https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
    ),
    "openai": EmbeddingModelProvider(
        name="openai",
        api_key="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
    ),
}

DEFAULT_RERANK_MODEL_PROVIDER: dict[str, RerankModelProvider] = {
    "dashscope": RerankModelProvider(
        name="dashscope",
        api_key="DASHSCOPE_API_KEY",
        endpoint="DASHSCOPE_RERANK_URL",
    ),
}


__all__ = [
    "DEFAULT_EMBEDDING_MODEL_PROVIDER",
    "DEFAULT_RERANK_MODEL_PROVIDER",
    "EmbeddingModelProvider",
    "RerankModelProvider",
]
