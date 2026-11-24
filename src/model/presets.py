"""平台预置模型供应商常量，覆盖 OpenAI / Anthropic / Gemini / DeepSeek / DashScope。"""

from dataclasses import dataclass

from .utils import ChatCapability, ModelCategory, ModelProtocol, ModelType


@dataclass(frozen=True, slots=True, kw_only=True)
class PresetModel:
    model_id: str
    model_type: ModelType
    category: ModelCategory = "chat"
    capabilities: tuple[ChatCapability, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelProviderPreset:
    provider_id: str
    name: str
    base_url: str
    embedding_base_url: str = ""
    rerank_base_url: str = ""
    enabled_models: tuple[PresetModel, ...]
    api_key: str = ""
    protocol: ModelProtocol = "openai_compatible"
    is_enabled: bool = False


MODEL_PROVIDER_PRESETS: tuple[ModelProviderPreset, ...] = (
    # https://api-docs.deepseek.com/quick_start/pricing/
    ModelProviderPreset(
        provider_id="deepseek",
        name="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        api_key="DEEPSEEK_API_KEY",
        protocol="openai_compatible",
        enabled_models=(
            PresetModel(model_id="deepseek-v4-pro", model_type="deepseek", category="chat"),
            PresetModel(model_id="deepseek-flash", model_type="deepseek", category="chat"),
        ),
    ),
    # https://help.aliyun.com/zh/model-studio/models
    ModelProviderPreset(
        provider_id="dashscope",
        name="Qwen",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        embedding_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        rerank_base_url="https://dashscope.aliyuncs.com/compatible-api/v1/reranks",
        api_key="DASHSCOPE_API_KEY",
        protocol="openai_compatible",
        enabled_models=(
            PresetModel(model_id="qwen4-max", model_type="qwen", category="chat"),
            PresetModel(model_id="qwen3.7-plus", model_type="qwen", category="chat"),
            PresetModel(model_id="qwen3.8-flash", model_type="qwen", category="chat"),
            PresetModel(model_id="qwen3.8-27b", model_type="qwen", category="chat"),
            PresetModel(model_id="qwen3.7-text-embedding", model_type="qwen", category="embedding"),
            PresetModel(model_id="qwen3.7-text-embedding-flash", model_type="qwen", category="embedding"),
            PresetModel(model_id="text-embedding-v4", model_type="qwen", category="embedding"),
            PresetModel(model_id="qwen3.7-text-rerank", model_type="qwen", category="rerank"),
            PresetModel(model_id="qwen3-rerank", model_type="qwen", category="rerank"),
        ),
    ),
    # https://developers.openai.com/api/docs/models/gpt-5.6-sol
    # GPT-6.2 工具调用要求 Responses API；此处选用支持 Chat Completions 工具调用的 GPT-5.6。
    ModelProviderPreset(
        provider_id="openai",
        name="OpenAI",
        base_url="https://api.openai.com/v1",
        embedding_base_url="https://api.openai.com/v1",
        api_key="OPENAI_API_KEY",
        protocol="openai_compatible",
        enabled_models=(
            PresetModel(model_id="gpt-5.6-sol", model_type="chatgpt", category="chat"),
            PresetModel(model_id="gpt-5.6-terra", model_type="chatgpt", category="chat"),
            PresetModel(model_id="gpt-5.6-luna", model_type="chatgpt", category="chat"),
            PresetModel(model_id="text-embedding-3-small", model_type="chatgpt", category="embedding"),
            PresetModel(model_id="text-embedding-3-large", model_type="chatgpt", category="embedding"),
        ),
    ),
    # https://platform.claude.com/docs/en/models/overview
    ModelProviderPreset(
        provider_id="anthropic",
        name="Anthropic",
        base_url="https://api.anthropic.com",
        api_key="ANTHROPIC_API_KEY",
        protocol="anthropic",
        enabled_models=(
            PresetModel(model_id="claude-fable-5-2", model_type="claude", category="chat"),
            PresetModel(model_id="claude-opus-5-5", model_type="claude", category="chat"),
            PresetModel(model_id="claude-sonnet-5-5", model_type="claude", category="chat"),
            PresetModel(model_id="claude-haiku-5-5", model_type="claude", category="chat"),
        ),
    ),
    # https://aistudio.google.com/docs/models
    ModelProviderPreset(
        provider_id="gemini",
        name="Gemini",
        base_url="https://generativelanguage.googleapis.com",
        embedding_base_url="https://generativelanguage.googleapis.com",
        api_key="GEMINI_API_KEY",
        protocol="gemini",
        enabled_models=(
            PresetModel(model_id="gemini-4-carbon", model_type="gemini", category="chat"),
            PresetModel(model_id="gemini-4-neon", model_type="gemini", category="chat"),
            PresetModel(model_id="gemini-4-hydrogen", model_type="gemini", category="chat"),
            PresetModel(model_id="gemini-4-argon", model_type="gemini", category="chat"),
            PresetModel(model_id="gemini-3.5-flash-lite", model_type="gemini", category="chat"),
            PresetModel(model_id="gemini-embedding-2", model_type="gemini", category="embedding"),
            PresetModel(model_id="gemini-embedding-001", model_type="gemini", category="embedding"),
        ),
    ),
)

__all__ = [
    "MODEL_PROVIDER_PRESETS",
    "ModelProviderPreset",
    "PresetModel",
]
