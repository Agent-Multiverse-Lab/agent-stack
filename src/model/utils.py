"""模型领域类型、参数校验与密钥解析辅助函数（不含 Pydantic DTO）。"""

import os
import re
from collections.abc import Sequence
from typing import Any, Literal, get_args
from urllib.parse import urlsplit

from src.configs import config as sys_config

ModelType = Literal[
    "deepseek",
    "qwen",
    "glm",
    "minomax",
    "gemini",
    "chatgpt",
    "claude",
    "ollama",
    "vllm",
]
ModelProtocol = Literal["openai_compatible", "anthropic", "gemini"]
ModelCategory = Literal["chat", "embedding", "rerank"]
ChatCapability = Literal[
    "chat",
    "vision",
    "reasoning",
    "tools",
    "code",
    "audio",
    "video",
]

_PROVIDER_ID_RE = re.compile(r"^[a-z0-9_-]{1,64}$")
_HEADER_NAME_RE = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")
_ENV_VAR_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
_VALID_MODEL_TYPES = frozenset(get_args(ModelType))
_VALID_PROTOCOLS = frozenset(get_args(ModelProtocol))
_VALID_CATEGORIES = frozenset(get_args(ModelCategory))
_VALID_CAPABILITIES = frozenset(get_args(ChatCapability))


def validate_provider_id(value: str) -> str:
    if not isinstance(value, str) or not _PROVIDER_ID_RE.fullmatch(value):
        raise ValueError("供应商 ID 格式无效")
    return value


def validate_name(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 255:
        raise ValueError("供应商名称不能为空且长度不能超过 255")
    return value.strip()


def validate_protocol(value: str) -> ModelProtocol:
    if not isinstance(value, str) or value not in _VALID_PROTOCOLS:
        raise ValueError(f"不支持的模型协议：{value}")
    return value  # type: ignore[return-value]


def validate_model_id(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise ValueError("模型 ID 必须非空且不得包含首尾空白或控制字符")
    return value


def validate_category(value: str) -> ModelCategory:
    if not isinstance(value, str) or value not in _VALID_CATEGORIES:
        raise ValueError(f"不支持的模型分类：{value}")
    return value  # type: ignore[return-value]


def validate_capabilities(value: Sequence[str]) -> list[ChatCapability]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("模型能力必须是列表")
    result: list[ChatCapability] = []
    seen: set[str] = set()
    for cap in value:
        if not isinstance(cap, str) or cap not in _VALID_CAPABILITIES:
            raise ValueError(f"不支持的模型能力：{cap}")
        if cap in seen:
            raise ValueError("模型能力不得重复")
        seen.add(cap)
        result.append(cap)  # type: ignore[arg-type]
    return result


def normalize_base_url(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("base_url 必须是字符串")
    try:
        url = urlsplit(value)
        valid = (
            url.scheme in {"http", "https"}
            and bool(url.hostname)
            and not url.username
            and not url.password
            and not url.query
            and not url.fragment
            and "?" not in value
            and "#" not in value
            and "@" not in url.netloc
            and not any(char.isspace() or ord(char) < 32 for char in value)
        )
        url.port
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(
            "base_url 必须是无用户信息、查询参数及 fragment 的 HTTP(S) 地址"
        )
    return value.rstrip("/")


def normalize_optional_url(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("URL 必须是字符串")
    if value == "":
        return ""
    return normalize_base_url(value)


def validate_api_key(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value.isascii()
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        or value != value.strip()
    ):
        raise ValueError("API Key 包含无效字符")
    return value


def validate_extra_headers(headers: dict[str, str]) -> dict[str, str]:
    if not isinstance(headers, dict):
        raise ValueError("extra_headers 必须是字典")
    seen: set[str] = set()
    for name, value in headers.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise ValueError("额外请求头键值必须是字符串")
        normalized = name.lower()
        if (
            not _HEADER_NAME_RE.fullmatch(name)
            or normalized in seen | {"host", "content-length", "authorization"}
            or not value.isascii()
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
            or value != value.strip()
        ):
            raise ValueError("额外请求头无效或包含受保护字段")
        seen.add(normalized)
    return dict(headers)


def normalize_enabled_models(
    models: Sequence[dict[str, Any]],
    *,
    require_model_type: bool = False,
    strip_legacy: bool = False,
) -> list[dict[str, Any]]:
    if isinstance(models, (str, bytes)) or not isinstance(models, Sequence):
        raise ValueError("models 必须是列表")
    allowed_keys = {"model_id", "category", "capabilities", "model_type"}
    if strip_legacy:
        allowed_keys = allowed_keys | {"body_overrides", "endpoint"}
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in models:
        if not isinstance(raw, dict):
            raise ValueError("模型配置项必须是字典")
        unknown = set(raw.keys()) - allowed_keys
        if unknown:
            raise ValueError(f"模型配置包含未知字段：{sorted(unknown)}")
        model_id = validate_model_id(raw.get("model_id", ""))
        if model_id in seen_ids:
            raise ValueError("同一供应商内模型 ID 不得重复")
        seen_ids.add(model_id)
        category = validate_category(raw.get("category", "chat"))
        capabilities = validate_capabilities(raw.get("capabilities", []))
        item: dict[str, Any] = {
            "model_id": model_id,
            "category": category,
            "capabilities": capabilities,
        }
        if "model_type" in raw and raw["model_type"] is not None:
            model_type = raw["model_type"]
            if not isinstance(model_type, str) or model_type not in _VALID_MODEL_TYPES:
                raise ValueError(f"不支持的模型类型：{model_type}")
            item["model_type"] = model_type
        elif require_model_type:
            raise ValueError("模型配置缺少 model_type")
        if strip_legacy and "endpoint" in raw and raw["endpoint"]:
            item["endpoint"] = raw["endpoint"]
        normalized.append(item)
    return normalized


def resolve_provider_api_key(value: str) -> str:
    """若配置值为已声明的环境变量名则读取对应密钥，否则按明文 API Key 返回。"""
    if not value:
        return ""
    if _ENV_VAR_NAME.fullmatch(value):
        if value in os.environ:
            return os.environ[value].strip()
        attr = value.lower()
        if hasattr(sys_config, attr):
            configured = getattr(sys_config, attr)
            if isinstance(configured, str):
                return configured.strip()
    return value


def resolve_chat_model_selection(
    *,
    model: str | None = None,
    conversation_model: str | None = None,
    agent_model: str | None = None,
) -> str:
    """依次选择 Run 快照、会话绑定、Agent 配置和配置文件默认模型。"""
    for candidate in (model, conversation_model, agent_model, sys_config.default_model):
        if candidate is None or candidate == "":
            continue
        if not isinstance(candidate, str) or candidate != candidate.strip():
            raise ValueError("模型配置必须是非空、无首尾空白的字符串")
        return candidate
    raise ValueError("未配置聊天模型")


__all__ = [
    "ChatCapability",
    "ModelCategory",
    "ModelProtocol",
    "ModelType",
    "normalize_base_url",
    "normalize_enabled_models",
    "normalize_optional_url",
    "resolve_chat_model_selection",
    "resolve_provider_api_key",
    "validate_api_key",
    "validate_capabilities",
    "validate_category",
    "validate_extra_headers",
    "validate_model_id",
    "validate_name",
    "validate_protocol",
    "validate_provider_id",
]
