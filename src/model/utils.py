"""模型领域类型、参数校验与密钥解析辅助函数（不含 Pydantic DTO）。"""

import os
import re
from collections.abc import Sequence
from typing import Any, Literal, get_args
from urllib.parse import urlsplit

from src.configs import config as sys_config

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
_ENV_VAR_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
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


def normalize_enabled_models(models: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(models, (str, bytes)) or not isinstance(models, Sequence):
        raise ValueError("models 必须是列表")
    allowed_keys = {"model_id", "category", "capabilities"}
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
        normalized.append(
            {
                "model_id": model_id,
                "category": category,
                "capabilities": capabilities,
            }
        )
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


def parse_model_ref(model_ref: str) -> tuple[str, str]:
    """解析并校验 provider_id:model_id 格式的模型引用，按第一个冒号切分。"""
    if not isinstance(model_ref, str) or not model_ref or model_ref != model_ref.strip():
        raise ValueError("模型引用必须为 provider_id:model_id")
    provider_id, separator, model_id = model_ref.partition(":")
    if (
        not separator
        or not _PROVIDER_ID_RE.fullmatch(provider_id)
        or not model_id
        or model_id != model_id.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in model_id)
    ):
        raise ValueError("模型引用必须为 provider_id:model_id")
    return provider_id, model_id


__all__ = [
    "ChatCapability",
    "ModelCategory",
    "ModelProtocol",
    "normalize_base_url",
    "normalize_enabled_models",
    "normalize_optional_url",
    "parse_model_ref",
    "resolve_provider_api_key",
    "validate_api_key",
    "validate_capabilities",
    "validate_category",
    "validate_model_id",
    "validate_name",
    "validate_protocol",
    "validate_provider_id",
]
