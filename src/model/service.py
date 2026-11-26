"""平台模型管理、预置补齐、目录缓存、模型发现、连通性探测与统一查库校验。"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Any, get_args

import httpx
from redis.exceptions import RedisError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import ModelProvider
from src.storage import get_async_redis_client
from src.utils import logger

from .model_provider.chat import supports_chat_protocol
from .presets import MODEL_PROVIDER_PRESETS
from .repository import ModelProviderRepository
from .utils import (
    ChatCapability,
    ModelCategory,
    ModelProtocol,
    normalize_base_url,
    normalize_enabled_models,
    normalize_optional_url,
    resolve_provider_api_key,
    validate_api_key,
    validate_category,
    validate_model_id,
    validate_name,
    validate_protocol,
    validate_provider_id,
)

MODEL_CATALOG_CACHE_KEY = "model:catalog:v1"
MODEL_LIST_CACHE_TTL_SECONDS = 3600


@dataclass(frozen=True, slots=True)
class ResolvedModel:
    """查库校验后的脱敏模型信息（不含明文凭据）。"""

    model_ref: str
    provider_id: str
    display_name: str
    model_id: str
    protocol: ModelProtocol
    category: ModelCategory
    capabilities: tuple[ChatCapability, ...] = ()


class ModelConnectionError(RuntimeError):
    """只暴露错误类别与状态码，避免上游响应或 URL 泄露凭据。"""

    def __init__(self, code: str, status_code: int | None = None):
        self.code = code
        self.status_code = status_code
        super().__init__(code)


class ModelProviderConflictError(ValueError):
    """模型供应商标识已存在。"""


def _provider_dict(provider: ModelProvider) -> dict[str, Any]:
    return {
        "provider_id": provider.provider_id,
        "name": provider.name,
        "protocol": provider.protocol,
        "base_url": provider.base_url or "",
        "embedding_base_url": provider.embedding_base_url or "",
        "rerank_base_url": provider.rerank_base_url or "",
        "is_enabled": bool(provider.is_enabled),
        "has_api_key": bool(resolve_provider_api_key(provider.api_key or "")),
        "models": [
            {
                "model_id": item["model_id"],
                "category": item.get("category", "chat"),
                "capabilities": list(item.get("capabilities") or []),
            }
            for item in (provider.enabled_models or [])
            if isinstance(item, dict) and isinstance(item.get("model_id"), str)
        ],
    }


async def get_enabled_model(
    db: AsyncSession,
    model_ref: str | None,
    *,
    category: ModelCategory,
) -> ResolvedModel:
    """业务层单一查库校验入口：确认模型已启用、属于目标分类并返回脱敏信息。"""
    if not isinstance(model_ref, str) or not model_ref:
        raise ValueError("未指定模型")
    provider, model = await ModelProviderRepository(db).require_model(
        model_ref, category=category
    )
    return ResolvedModel(
        model_ref=f"{provider.provider_id}:{model['model_id']}",
        provider_id=str(provider.provider_id),
        display_name=str(provider.name),
        model_id=str(model["model_id"]),
        protocol=provider.protocol,
        category=model.get("category", "chat"),
        capabilities=tuple(model.get("capabilities") or ()),
    )


def _filter_catalog(
    catalog: dict[str, dict[str, Any]],
    category: ModelCategory,
) -> dict[str, dict[str, Any]]:
    filtered: dict[str, dict[str, Any]] = {}
    for provider_id, entry in catalog.items():
        models = [
            {
                "model_id": item["model_id"],
                "category": item["category"],
                "capabilities": list(item["capabilities"]),
            }
            for item in entry["models"]
            if item["category"] == category
        ]
        if models:
            filtered[provider_id] = {
                "provider_id": entry["provider_id"],
                "display_name": entry["display_name"],
                "models": models,
            }
    return filtered


def _is_valid_catalog(parsed: Any) -> bool:
    if not isinstance(parsed, dict):
        return False
    for provider_id, entry in parsed.items():
        if (
            not isinstance(provider_id, str)
            or not isinstance(entry, dict)
            or entry.get("provider_id") != provider_id
            or not isinstance(entry.get("display_name"), str)
            or not isinstance(entry.get("models"), list)
        ):
            return False
        for item in entry["models"]:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("model_id"), str)
                or not item["model_id"]
                or item.get("category") not in {"chat", "embedding", "rerank"}
                or not isinstance(item.get("capabilities"), list)
            ):
                return False
    return True


async def build_model_catalog(
    db: AsyncSession,
    *,
    category: ModelCategory | None = None,
) -> dict[str, dict[str, Any]]:
    """从 PostgreSQL 构建按厂商分组的已启用脱敏模型目录。"""
    resolved_category = validate_category(category) if category is not None else None
    catalog: dict[str, dict[str, Any]] = {}
    for provider in await ModelProviderRepository(db).list_model_providers(enabled_only=True):
        chat_supported = supports_chat_protocol(provider.protocol)
        models: list[dict[str, Any]] = []
        for model in provider.enabled_models or []:
            if not isinstance(model, dict):
                continue
            model_id = model.get("model_id")
            item_category = model.get("category", "chat")
            if not isinstance(model_id, str) or not model_id:
                continue
            if item_category == "chat" and not chat_supported:
                continue
            if resolved_category is not None and item_category != resolved_category:
                continue
            models.append(
                {
                    "model_id": model_id,
                    "category": item_category,
                    "capabilities": list(model.get("capabilities") or []),
                }
            )
        if models:
            catalog[str(provider.provider_id)] = {
                "provider_id": str(provider.provider_id),
                "display_name": str(provider.name),
                "models": models,
            }
    return catalog


async def _write_model_list_cache(catalog: dict[str, Any]) -> None:
    redis = await get_async_redis_client()
    await redis.set(
        MODEL_CATALOG_CACHE_KEY,
        json.dumps(catalog, ensure_ascii=False),
        ex=MODEL_LIST_CACHE_TTL_SECONDS,
    )


async def list_models(
    db: AsyncSession,
    *,
    category: ModelCategory = "chat",
) -> dict[str, dict[str, Any]]:
    """读取全量已启用模型目录（按 category 过滤）；缓存失效或不可用时回源 PostgreSQL。"""
    resolved_category = validate_category(category)
    try:
        redis = await get_async_redis_client()
        cached = await redis.get(MODEL_CATALOG_CACHE_KEY)
        if cached is not None:
            try:
                raw = cached.decode() if isinstance(cached, (bytes, bytearray)) else cached
                parsed = json.loads(raw)
                if _is_valid_catalog(parsed):
                    return _filter_catalog(parsed, resolved_category)
                logger.warning("模型目录缓存结构无效，已回源 PostgreSQL")
            except (ValueError, UnicodeDecodeError):
                logger.warning("模型目录缓存结构无效，已回源 PostgreSQL")
    except (RedisError, OSError, ValueError) as exc:
        logger.warning("模型目录 Redis 读取失败，已回源 PostgreSQL：%s", exc)

    catalog = await build_model_catalog(db)
    try:
        await _write_model_list_cache(catalog)
    except (RedisError, OSError, ValueError) as exc:
        logger.warning("模型目录 Redis 回填失败：%s", exc)
    return _filter_catalog(catalog, resolved_category)


async def refresh_model_list_cache(
    db: AsyncSession,
    *,
    raise_on_database_error: bool = False,
) -> bool:
    """从已提交数据重建全量已启用模型目录缓存。"""
    try:
        catalog = await build_model_catalog(db)
        redis = await get_async_redis_client()
        await redis.delete(MODEL_CATALOG_CACHE_KEY)
        await _write_model_list_cache(catalog)
    except (SQLAlchemyError, ValueError) as exc:
        if raise_on_database_error:
            raise
        logger.warning("模型目录缓存重建失败：%s", exc)
        return False
    except (RedisError, OSError) as exc:
        logger.warning("模型目录 Redis 刷新失败：%s", exc)
        return False
    return True


async def ensure_builtin_model_providers(db: AsyncSession) -> None:
    """启动时幂等补齐缺失的内置模型供应商预置行，不覆盖既有配置。"""
    repository = ModelProviderRepository(db)
    try:
        existing_ids = {
            provider.provider_id for provider in await repository.list_model_providers()
        }
        missing = [
            preset for preset in MODEL_PROVIDER_PRESETS if preset.provider_id not in existing_ids
        ]
        if missing:
            for preset in missing:
                await repository.create_model_provider(
                    provider_id=preset.provider_id,
                    name=preset.name.strip(),
                    base_url=preset.base_url.rstrip("/"),
                    embedding_base_url=preset.embedding_base_url.rstrip("/"),
                    rerank_base_url=preset.rerank_base_url.rstrip("/"),
                    protocol=preset.protocol,
                    api_key=preset.api_key,
                    extra_headers={},
                    is_enabled=preset.is_enabled,
                    enabled_models=[
                        {
                            "model_id": model.model_id,
                            "category": model.category,
                            "capabilities": list(model.capabilities),
                        }
                        for model in preset.enabled_models
                    ],
                )
            await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise RuntimeError("补齐模型供应商失败") from None


async def get_model_provider(
    db: AsyncSession,
    provider_id: str,
) -> dict[str, Any]:
    provider = await ModelProviderRepository(db).get_model_provider_by_id(provider_id)
    if provider is None:
        raise LookupError("模型供应商不存在")
    return _provider_dict(provider)


async def list_model_providers(db: AsyncSession) -> list[dict[str, Any]]:
    providers = await ModelProviderRepository(db).list_model_providers()
    return [_provider_dict(provider) for provider in providers]


async def create_model_provider(
    db: AsyncSession,
    *,
    provider_id: str,
    name: str,
    base_url: str,
    protocol: str = "openai_compatible",
    embedding_base_url: str = "",
    rerank_base_url: str = "",
    is_enabled: bool = False,
    models: Sequence[dict[str, Any]] = (),
    api_key: str = "",
) -> dict[str, Any]:
    """创建平台模型供应商配置并刷新全局目录缓存。"""
    if not isinstance(is_enabled, bool):
        raise ValueError("is_enabled 必须是布尔值")
    pid = validate_provider_id(provider_id)
    record = {
        "provider_id": pid,
        "name": validate_name(name),
        "protocol": validate_protocol(protocol),
        "base_url": normalize_base_url(base_url),
        "embedding_base_url": normalize_optional_url(embedding_base_url),
        "rerank_base_url": normalize_optional_url(rerank_base_url),
        "api_key": validate_api_key(api_key),
        "extra_headers": {},
        "is_enabled": is_enabled,
        "enabled_models": normalize_enabled_models(models),
    }
    try:
        await ModelProviderRepository(db).create_model_provider(**record)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ModelProviderConflictError("模型供应商已存在") from None
    except SQLAlchemyError:
        await db.rollback()
        raise RuntimeError("保存模型供应商失败") from None
    return {
        "provider_id": pid,
        "cache_refreshed": await refresh_model_list_cache(db),
    }


async def _request_json(
    base_url: str,
    headers: dict[str, str],
    path: str,
    *,
    body: dict[str, Any] | None = None,
) -> Any:
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False, trust_env=False) as client:
            response = await client.request(
                "GET" if body is None else "POST",
                f"{base_url.rstrip('/')}{path}",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        raise ModelConnectionError("timeout") from None
    except httpx.HTTPStatusError as exc:
        raise ModelConnectionError("http_error", exc.response.status_code) from None
    except httpx.RequestError:
        raise ModelConnectionError("connection_error") from None
    except ValueError:
        raise ModelConnectionError("invalid_response") from None
    except (OSError, TimeoutError):
        raise ModelConnectionError("connection_error") from None


def _explicit_non_chat(item: dict[str, Any]) -> bool:
    non_chat = {"embedding", "embeddings", "rerank", "reranking", "image-generation", "text-to-speech", "speech-to-text"}
    for field in ("type", "task"):
        if isinstance(item.get(field), str) and item[field].lower() in non_chat:
            return True
    capabilities = item.get("capabilities")
    if isinstance(capabilities, dict):
        return capabilities.get("chat") is False
    if isinstance(capabilities, list):
        labels = {value.lower() for value in capabilities if isinstance(value, str)}
        return bool(labels & non_chat) and not labels & {"chat", "text-generation"}
    return False


async def _resolve_remote_config(
    db: AsyncSession,
    provider_id: str,
    *,
    base_url: str,
    api_key: str | None = None,
    api_key_provided: bool = False,
    protocol: str | None = None,
) -> dict[str, Any]:
    provider = await ModelProviderRepository(db).get_model_provider_by_id(provider_id)
    if provider is None:
        raise LookupError("模型供应商不存在")
    resolved_protocol = validate_protocol(protocol) if protocol is not None else provider.protocol
    normalized_base = normalize_base_url(base_url)
    if api_key_provided:
        if api_key is None:
            raise ValueError("API Key 不可为 null")
        validated_key = validate_api_key(api_key)
    else:
        validated_key = provider.api_key or ""

    extra_headers = dict(getattr(provider, "extra_headers", None) or {})
    if normalized_base != provider.base_url:
        if resolve_provider_api_key(provider.api_key or "") and not api_key_provided:
            raise ValueError("更改服务地址后必须重新提供 API Key")
        extra_headers = {}

    return {
        "protocol": resolved_protocol,
        "base_url": normalized_base,
        "extra_headers": extra_headers,
        "api_key": validated_key,
    }


async def update_model_provider(
    db: AsyncSession,
    provider_id: str,
    *,
    base_url: str,
    embedding_base_url: str = "",
    rerank_base_url: str = "",
    is_enabled: bool = False,
    models: Sequence[dict[str, Any]] = (),
    api_key: str | None = None,
    api_key_provided: bool = False,
    name: str | None = None,
    protocol: str | None = None,
) -> dict[str, Any]:
    """更新平台模型供应商配置并刷新全局目录缓存。"""
    provider = await ModelProviderRepository(db).get_model_provider_by_id(provider_id)
    if provider is None:
        raise LookupError("模型供应商不存在")
    if not isinstance(is_enabled, bool):
        raise ValueError("is_enabled 必须是布尔值")
    resolved_name = validate_name(name) if name is not None else provider.name
    resolved_protocol = validate_protocol(protocol) if protocol is not None else provider.protocol
    normalized_base = normalize_base_url(base_url)
    normalized_embedding = normalize_optional_url(embedding_base_url)
    normalized_rerank = normalize_optional_url(rerank_base_url)
    if api_key_provided:
        if api_key is None:
            raise ValueError("API Key 不可为 null")
        validated_key = validate_api_key(api_key)
    else:
        validated_key = None

    urls_changed = (
        normalized_base != provider.base_url
        or normalized_embedding != (getattr(provider, "embedding_base_url", "") or "")
        or normalized_rerank != (getattr(provider, "rerank_base_url", "") or "")
    )
    extra_headers = dict(getattr(provider, "extra_headers", None) or {})
    if urls_changed:
        if resolve_provider_api_key(provider.api_key or "") and not api_key_provided:
            raise ValueError("更改服务地址后必须重新提供 API Key")
        extra_headers = {}

    update_fields: dict[str, Any] = {
        "name": resolved_name,
        "protocol": resolved_protocol,
        "base_url": normalized_base,
        "embedding_base_url": normalized_embedding,
        "rerank_base_url": normalized_rerank,
        "extra_headers": extra_headers,
        "is_enabled": is_enabled,
        "enabled_models": normalize_enabled_models(models),
    }
    if validated_key is not None:
        update_fields["api_key"] = validated_key
    try:
        updated = await ModelProviderRepository(db).update_model_provider(provider_id, **update_fields)
        if updated is None:
            raise LookupError("模型供应商不存在")
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise RuntimeError("更新模型供应商失败") from None
    return {
        "provider_id": provider_id,
        "cache_refreshed": await refresh_model_list_cache(db),
    }


async def delete_model_provider(db: AsyncSession, provider_id: str) -> dict[str, Any]:
    """删除平台模型供应商并刷新全局目录缓存。"""
    try:
        deleted = await ModelProviderRepository(db).delete_model_provider(provider_id)
        if not deleted:
            raise LookupError("模型供应商不存在")
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise RuntimeError("删除模型供应商失败") from None
    return {
        "provider_id": provider_id,
        "cache_refreshed": await refresh_model_list_cache(db),
    }


async def discover_provider_models(
    db: AsyncSession,
    provider_id: str,
    *,
    base_url: str,
    api_key: str | None = None,
    api_key_provided: bool = False,
    protocol: str | None = None,
) -> list[dict[str, Any]]:
    config = await _resolve_remote_config(
        db,
        provider_id,
        base_url=base_url,
        api_key=api_key,
        api_key_provided=api_key_provided,
        protocol=protocol,
    )
    return await _discover_config_models(config)


async def _discover_config_models(config: dict[str, Any]) -> list[dict[str, Any]]:
    headers = dict(config["extra_headers"])
    key = resolve_provider_api_key(config.get("api_key") or "")
    protocol = config["protocol"]
    base_url = config["base_url"]
    if protocol == "anthropic":
        if key:
            headers["x-api-key"] = key
        headers.setdefault("anthropic-version", "2023-06-01")
        path = "/models" if base_url.endswith("/v1") else "/v1/models"
        payload = await _request_json(base_url, headers, path)
        raw_items = payload.get("data") if isinstance(payload, dict) else None
    elif protocol == "gemini":
        if key:
            headers["x-goog-api-key"] = key
        path = "/models" if base_url.endswith("/v1beta") else "/v1beta/models"
        payload = await _request_json(base_url, headers, path)
        raw_items = payload.get("models") if isinstance(payload, dict) else None
    else:
        if key:
            headers["Authorization"] = f"Bearer {key}"
        payload = await _request_json(base_url, headers, "/models")
        raw_items = payload.get("data") if isinstance(payload, dict) else None

    if not isinstance(raw_items, list):
        raise ModelConnectionError("invalid_response")

    models: dict[str, dict[str, Any]] = {}
    for item in raw_items:
        if not isinstance(item, dict):
            raise ModelConnectionError("invalid_response")
        if protocol == "gemini":
            raw_name = item.get("name")
            if not isinstance(raw_name, str) or not raw_name:
                raise ModelConnectionError("invalid_response")
            model_id = raw_name.removeprefix("models/")
            methods = item.get("supportedGenerationMethods")
            if isinstance(methods, list) and "generateContent" not in methods:
                continue
            capabilities: list[ChatCapability] = ["chat"]
        else:
            model_id = item.get("id")
            if not isinstance(model_id, str) or not model_id:
                raise ModelConnectionError("invalid_response")
            if _explicit_non_chat(item):
                continue
            metadata = item.get("capabilities", [])
            if isinstance(metadata, dict):
                metadata = [k for k, v in metadata.items() if v is True]
            labels = {v for v in metadata if isinstance(v, str)} if isinstance(metadata, list) else set()
            capabilities = [label for label in get_args(ChatCapability) if label in labels]

        try:
            validate_model_id(model_id)
        except ValueError:
            raise ModelConnectionError("invalid_response") from None
        models[model_id] = {
            "model_id": model_id,
            "category": "chat",
            "capabilities": capabilities,
        }
    return [models[key] for key in sorted(models)]


async def test_provider_connection(
    db: AsyncSession,
    provider_id: str,
    *,
    base_url: str,
    api_key: str | None = None,
    api_key_provided: bool = False,
    protocol: str | None = None,
) -> dict[str, Any]:
    config = await _resolve_remote_config(
        db,
        provider_id,
        base_url=base_url,
        api_key=api_key,
        api_key_provided=api_key_provided,
        protocol=protocol,
    )
    started = perf_counter()
    try:
        await _discover_config_models(config)
    except ModelConnectionError as exc:
        return {
            "success": False,
            "elapsed_ms": (perf_counter() - started) * 1000,
            "error": exc.code,
            "status_code": exc.status_code,
        }
    return {
        "success": True,
        "elapsed_ms": (perf_counter() - started) * 1000,
        "error": None,
        "status_code": None,
    }
