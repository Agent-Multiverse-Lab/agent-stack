"""模型目录展示元数据与 Redis read-through cache。"""

from __future__ import annotations

import json
import re
from typing import Any

from redis.exceptions import RedisError

from src.configs import DEFAULT_BASE_MODEL_PROVIER
from src.configs import config as sys_config
from src.storage import get_async_redis_client
from src.utils import logger

MODEL_CATALOG_CACHE_KEY = "model:catalog:v1"
MODEL_CATALOG_CACHE_TTL_SECONDS = 3600

_SUPPORTED_CHAT_PROVIDERS = frozenset({"dashscope", "deepseek", "openai"})

_MODEL_FAMILIES = (
    ("deepseek", "DeepSeek", "deepseek"),
    ("gemini", "Gemini", "gemini"),
    ("qwen", "Qwen", "qwen"),
    ("gpt", "GPT", "openai"),
)


def _format_version_token(token: str) -> str:
    if re.fullmatch(r"v\d+(?:\.\d+)?", token):
        return token.upper()
    if re.fullmatch(r"\d+(?:\.\d+)?b", token):
        return token.upper()
    if re.fullmatch(r"a\d+b", token):
        return token.upper()
    if re.fullmatch(r"\d+(?:\.\d+)?[a-z]", token):
        return token
    if re.fullmatch(r"\d+(?:\.\d+)?", token):
        return token
    return token.capitalize()


def _model_presentation(
    model_name: str,
    provider_name: str,
) -> tuple[str, str, str]:
    normalized_name = model_name.lower()
    for prefix, display_name, icon in _MODEL_FAMILIES:
        if normalized_name.startswith(prefix):
            raw_version = model_name[len(prefix) :].lstrip("-")
            version = " ".join(
                _format_version_token(token)
                for token in raw_version.split("-")
                if token
            )
            return display_name, version or model_name, icon

    display_name = provider_name.replace("_", " ").title()
    return display_name, model_name, provider_name.lower()


def build_model_catalog() -> dict[str, Any]:
    """从当前 Provider 配置构建公开模型目录。"""
    models: list[dict[str, Any]] = []
    for provider_name, provider in DEFAULT_BASE_MODEL_PROVIER.items():
        for model_name in provider.model_list:
            model_id = f"{provider_name}/{model_name}"
            display_name, version, icon = _model_presentation(
                model_name,
                provider_name,
            )
            models.append(
                {
                    "id": model_id,
                    "name": model_name,
                    "display_name": display_name,
                    "version": version,
                    "provider": provider_name,
                    "icon": icon,
                    "is_available": provider_name in _SUPPORTED_CHAT_PROVIDERS,
                    "is_default": model_id == sys_config.default_model,
                    "is_fallback": model_id == sys_config.fallback_model,
                    "is_flash": model_id == sys_config.flash_model,
                }
            )

    return {
        "default_model": sys_config.default_model,
        "fallback_model": sys_config.fallback_model,
        "flash_model": sys_config.flash_model,
        "image_model": sys_config.image_model,
        "models": models,
    }


def is_model_available(model_id: str) -> bool:
    """判断 model ID 是否存在且可由当前 ChatModel loader 构造。"""
    return any(
        provider_name in _SUPPORTED_CHAT_PROVIDERS
        and model_id == f"{provider_name}/{model_name}"
        for provider_name, provider in DEFAULT_BASE_MODEL_PROVIER.items()
        for model_name in provider.model_list
    )


def _decode_cached_catalog(raw: bytes | str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
        return None
    return payload


async def get_model_catalog() -> dict[str, Any]:
    """优先读取 Redis；缓存缺失或失效时从 config 重建并回填。"""
    try:
        redis = await get_async_redis_client()
        cached = await redis.get(MODEL_CATALOG_CACHE_KEY)
        if cached is not None:
            cached_catalog = _decode_cached_catalog(cached)
            if cached_catalog is not None:
                return cached_catalog

        catalog = build_model_catalog()
        await redis.set(
            MODEL_CATALOG_CACHE_KEY,
            json.dumps(catalog, ensure_ascii=False),
            ex=MODEL_CATALOG_CACHE_TTL_SECONDS,
        )
        return catalog
    except (RedisError, OSError, ValueError) as exc:
        logger.warning("模型目录 Redis 缓存不可用，已回退 config：%s", exc)
        return build_model_catalog()


__all__ = [
    "MODEL_CATALOG_CACHE_KEY",
    "MODEL_CATALOG_CACHE_TTL_SECONDS",
    "build_model_catalog",
    "get_model_catalog",
    "is_model_available",
]
