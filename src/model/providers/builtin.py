"""供应商首次创建值；字段映射和校验由 Model Service 显式执行。"""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import JsonValue

ModelType = Literal["deepseek", "qwen", "glm", "minomax", "gemini", "chatgpt", "ollama", "vllm"]
ModelProtocol = Literal["openai_compatible"]
ChatCapability = Literal["chat", "vision", "reasoning", "tools", "code", "audio", "video"]


@dataclass(frozen=True, slots=True, kw_only=True)
class PresetChatModel:
    model_id: str
    model_type: ModelType
    body_overrides: dict[str, JsonValue] = field(default_factory=dict)
    capabilities: tuple[ChatCapability, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelProviderPreset:
    provider_id: str
    name: str
    base_url: str
    enabled_models: tuple[PresetChatModel, ...]
    protocol: ModelProtocol = "openai_compatible"
    is_enabled: bool = False


MODEL_PROVIDER_PRESETS: tuple[ModelProviderPreset, ...] = (
    ModelProviderPreset(
        provider_id="deepseek",
        name="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        enabled_models=(
            PresetChatModel(model_id="deepseek-v4-pro", model_type="deepseek"),
            PresetChatModel(model_id="deepseek-v4-flash", model_type="deepseek"),
        ),
    ),
    ModelProviderPreset(
        provider_id="qwen",
        name="Qwen",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        enabled_models=(
            PresetChatModel(model_id="qwen3.6-plus", model_type="qwen"),
            PresetChatModel(model_id="qwen3.5-27b", model_type="qwen"),
            PresetChatModel(model_id="qwen3.6-35b-a3b", model_type="qwen"),
            PresetChatModel(model_id="qwen3.8-max", model_type="qwen"),
        ),
    ),
)
