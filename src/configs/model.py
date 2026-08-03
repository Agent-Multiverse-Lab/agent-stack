from pydantic import BaseModel, Field


class BaseModelProvider(BaseModel):
    name: str = Field(..., description="模型名称")
    api_key: str = Field(..., description="API密钥")
    default_model: str = Field(..., description="默认模型")
    base_url: str = Field(..., description="API基础URL")
    model_list: list[str] = Field(..., description="模型列表")


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


DEFAULT_BASE_MODEL_PROVIER: dict[str, BaseModelProvider] = {
    # 阿里
    "dashscope": BaseModelProvider(
        name="dashscope",
        api_key="DASHSCOPE_API_KEY",
        default_model="qwen3.6-plus",
        base_url="https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        model_list=[
            "qwen3.6-plus",
        ],
    ),
    
    # deepseek
    "deepseek": BaseModelProvider(
        name="deepseek",
        api_key="DEEPSEEK_API_KEY",
        default_model="deepseek-v4-pro",
        base_url="https://api.deepseek.com/v1",
        model_list=["deepseek-v4-pro", "deepseek-v4-flash"],
    ),
    # openai
    "openai": BaseModelProvider(
        name="openai",
        api_key="OPENAI_API_KEY",
        default_model="gpt-4o",
        base_url="https://api.openai.com/v1",
        model_list=["gpt-4o", "gpt-4o-mini"],
    ),
    # 谷歌
    "gemini": BaseModelProvider(
        name="gemini",
        api_key="GEMINI_API_KEY",
        default_model="gemini-3-pro",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        model_list=[
            "gemini-3.1-pro",
            "gemini-3-pro",
            "gemini-3-flash",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
        ],
    ),
}

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
    "BaseModelProvider",
    "DEFAULT_BASE_MODEL_PROVIER",
    "DEFAULT_EMBEDDING_MODEL_PROVIDER",
    "DEFAULT_RERANK_MODEL_PROVIDER",
    "EmbeddingModelProvider",
    "RerankModelProvider",
]
