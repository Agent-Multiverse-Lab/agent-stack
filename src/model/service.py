"""平台模型管理、预置补齐、目录缓存、模型发现与连通性探测。"""

import json
from collections.abc import Sequence
from time import perf_counter
from typing import Any, get_args

import httpx
from redis.exceptions import RedisError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.configs import config as sys_config
from src.database.models import ModelProvider
from src.storage import get_async_redis_client
from src.utils import logger

from .model_provider.chat import build_chat_model, supports_chat_protocol
from .model_provider.embedding import EmbeddingError, build_embedding_model
from .model_provider.reranker import RerankDocument, RerankError, build_reranker
from .presets import MODEL_PROVIDER_PRESETS
from .repository import ModelProviderRepository
from .runtime import _resolve
from .utils import (
    ChatCapability,
    ModelCategory,
    normalize_base_url,
    normalize_enabled_models,
    normalize_optional_url,
    resolve_provider_api_key,
    validate_api_key,
    validate_extra_headers,
    validate_model_id,
    validate_name,
    validate_protocol,
    validate_provider_id,
)

MODEL_LIST_CACHE_KEY = "model:chat:list:v4"
MODEL_LIST_CACHE_TTL_SECONDS = 3600


class ModelConnectionError(RuntimeError):
    """只暴露错误类别与状态码，避免上游响应或 URL 泄露凭据。"""

    def __init__(self, code: str, status_code: int | None = None):
        self.code = code
        self.status_code = status_code
        super().__init__(code)


def _is_valid_cached_model_list(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if not isinstance(payload.get("default_model"), str) or not isinstance(payload.get("flash_model"), str):
        return False
    models = payload.get("models")
    if not isinstance(models, list):
        return False
    for item in models:
        if not isinstance(item, dict):
            return False
        if not (
            isinstance(item.get("id"), str)
            and isinstance(item.get("name"), str)
            and isinstance(item.get("provider"), str)
            and isinstance(item.get("is_available"), bool)
        ):
            return False
    return True


def _provider_dict(provider: ModelProvider) -> dict[str, Any]:
    return {
        "provider_id": provider.provider_id,
        "name": provider.name,
        "base_url": provider.base_url or "",
        "embedding_base_url": getattr(provider, "embedding_base_url", "") or "",
        "rerank_base_url": getattr(provider, "rerank_base_url", "") or "",
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


async def build_model_list(
    db: AsyncSession,
    *,
    category: ModelCategory = "chat",
) -> dict[str, Any]:
    """从 PostgreSQL 构建不含连接参数的公开模型列表（默认仅 Chat 模型）。"""
    models: list[dict[str, Any]] = []
    for provider in await ModelProviderRepository(db).list_model_providers(enabled_only=True):
        protocol = validate_protocol(provider.protocol)
        available = supports_chat_protocol(protocol)
        enabled_models = normalize_enabled_models(
            list(getattr(provider, "enabled_models", None) or []),
            strip_legacy=True,
        )
        for model in enabled_models:
            if model["category"] != category:
                continue
            models.append(
                {
                    "id": f"{provider.provider_id}/{model['model_id']}",
                    "name": model["model_id"],
                    "provider": provider.provider_id,
                    "is_available": available,
                }
            )

    available_ids = [item["id"] for item in models if item["is_available"]]
    default_model = (
        sys_config.default_model
        if sys_config.default_model in available_ids
        else available_ids[0]
        if available_ids
        else ""
    )
    flash_model = (
        sys_config.flash_model if sys_config.flash_model in available_ids else ""
    )
    return {
        "default_model": default_model,
        "flash_model": flash_model,
        "models": models,
    }


async def _write_model_list_cache(catalog: dict[str, Any]) -> None:
    redis = await get_async_redis_client()
    await redis.set(
        MODEL_LIST_CACHE_KEY,
        json.dumps(catalog, ensure_ascii=False),
        ex=MODEL_LIST_CACHE_TTL_SECONDS,
    )


async def list_models(db: AsyncSession) -> dict[str, Any]:
    """读取全局模型列表；缓存失效或不可用时回源 PostgreSQL。"""
    try:
        redis = await get_async_redis_client()
        cached = await redis.get(MODEL_LIST_CACHE_KEY)
        if cached is not None:
            try:
                raw = cached.decode() if isinstance(cached, (bytes, bytearray)) else cached
                parsed = json.loads(raw)
                if _is_valid_cached_model_list(parsed):
                    return parsed
                logger.warning("模型列表缓存结构无效，已回源 PostgreSQL")
            except (ValueError, UnicodeDecodeError):
                logger.warning("模型列表缓存结构无效，已回源 PostgreSQL")
    except (RedisError, OSError, ValueError) as exc:
        logger.warning("模型列表 Redis 读取失败，已回源 PostgreSQL：%s", exc)

    catalog = await build_model_list(db)
    try:
        await _write_model_list_cache(catalog)
    except (RedisError, OSError, ValueError) as exc:
        logger.warning("模型列表 Redis 回填失败：%s", exc)
    return catalog


async def refresh_model_list_cache(
    db: AsyncSession,
    *,
    raise_on_database_error: bool = False,
) -> bool:
    """从已提交数据重建全局模型列表缓存。"""
    try:
        catalog = await build_model_list(db)
        redis = await get_async_redis_client()
        await redis.delete(MODEL_LIST_CACHE_KEY)
        await _write_model_list_cache(catalog)
    except (SQLAlchemyError, ValueError) as exc:
        if raise_on_database_error:
            raise
        logger.warning("模型列表缓存重建失败：%s", exc)
        return False
    except (RedisError, OSError) as exc:
        logger.warning("模型列表 Redis 刷新失败：%s", exc)
        return False
    return True


async def ensure_builtin_model_providers(db: AsyncSession) -> None:
    """显式校验全部预置并补齐缺失行。"""
    pending: list[dict[str, Any]] = []
    seen: set[str] = set()
    for preset in MODEL_PROVIDER_PRESETS:
        provider_id = validate_provider_id(preset.provider_id)
        if provider_id in seen:
            raise ValueError("预置供应商 ID 不得重复")
        if not isinstance(preset.is_enabled, bool):
            raise ValueError("is_enabled 必须是布尔值")
        enabled_models = normalize_enabled_models(
            [
                {
                    "model_id": model.model_id,
                    "category": model.category,
                    "model_type": model.model_type,
                    "capabilities": list(model.capabilities),
                }
                for model in preset.enabled_models
            ],
            require_model_type=True,
        )
        if not enabled_models:
            raise ValueError("预置模型列表不能为空")
        seen.add(provider_id)
        pending.append(
            {
                "provider_id": provider_id,
                "name": validate_name(preset.name),
                "base_url": normalize_base_url(preset.base_url),
                "embedding_base_url": normalize_optional_url(preset.embedding_base_url),
                "rerank_base_url": normalize_optional_url(preset.rerank_base_url),
                "protocol": validate_protocol(preset.protocol),
                "api_key": validate_api_key(preset.api_key),
                "extra_headers": {},
                "is_enabled": preset.is_enabled,
                "enabled_models": enabled_models,
            }
        )

    repository = ModelProviderRepository(db)
    try:
        existing_ids = {
            provider.provider_id for provider in await repository.list_model_providers()
        }
        missing = [
            item for item in pending if item["provider_id"] not in existing_ids
        ]
        if missing:
            for item in missing:
                await repository.create_model_provider(**item)
            await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise RuntimeError("补齐模型供应商失败") from None


async def _get_model_provider(db: AsyncSession, provider_id: str) -> ModelProvider:
    provider = await ModelProviderRepository(db).get_model_provider_by_id(provider_id)
    if provider is None:
        raise LookupError("模型供应商不存在")
    return provider


async def get_model_provider(db: AsyncSession, provider_id: str) -> dict[str, Any]:
    return _provider_dict(await _get_model_provider(db, provider_id))


async def list_model_providers(db: AsyncSession) -> list[dict[str, Any]]:
    return [
        _provider_dict(provider)
        for provider in await ModelProviderRepository(db).list_model_providers()
    ]


async def create_model_provider(
    db: AsyncSession,
    /,
    **values: Any,
) -> dict[str, Any]:
    provider_id = validate_provider_id(values.get("provider_id", ""))
    is_enabled = values.get("is_enabled", False)
    if not isinstance(is_enabled, bool):
        raise ValueError("is_enabled 必须是布尔值")
    record = {
        "provider_id": provider_id,
        "name": validate_name(values.get("name", "")),
        "base_url": normalize_base_url(values.get("base_url", "")),
        "embedding_base_url": normalize_optional_url(values.get("embedding_base_url", "")),
        "rerank_base_url": normalize_optional_url(values.get("rerank_base_url", "")),
        "protocol": validate_protocol(values.get("protocol", "openai_compatible")),
        "api_key": validate_api_key(values.get("api_key", "")),
        "extra_headers": validate_extra_headers(dict(values.get("extra_headers") or {})),
        "is_enabled": is_enabled,
        "enabled_models": normalize_enabled_models(
            list(values.get("enabled_models") or []),
            require_model_type=True,
        ),
    }
    try:
        await ModelProviderRepository(db).create_model_provider(**record)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ValueError("供应商 ID 已存在") from None
    except SQLAlchemyError:
        await db.rollback()
        raise RuntimeError("保存模型供应商失败") from None
    return {
        "provider_id": provider_id,
        "cache_refreshed": await refresh_model_list_cache(db),
    }


async def update_model_provider(
    db: AsyncSession,
    provider_id: str,
    /,
    **values: Any,
) -> dict[str, Any]:
    provider = await _get_model_provider(db, provider_id)
    update_fields: dict[str, Any] = {}
    if "name" in values:
        update_fields["name"] = validate_name(values["name"])
    if "base_url" in values:
        update_fields["base_url"] = normalize_base_url(values["base_url"])
    if "embedding_base_url" in values:
        update_fields["embedding_base_url"] = normalize_optional_url(values["embedding_base_url"])
    if "rerank_base_url" in values:
        update_fields["rerank_base_url"] = normalize_optional_url(values["rerank_base_url"])
    if "protocol" in values:
        update_fields["protocol"] = validate_protocol(values["protocol"])
    if "extra_headers" in values:
        update_fields["extra_headers"] = validate_extra_headers(dict(values["extra_headers"] or {}))
    if "is_enabled" in values:
        if not isinstance(values["is_enabled"], bool):
            raise ValueError("is_enabled 必须是布尔值")
        update_fields["is_enabled"] = values["is_enabled"]
    if "enabled_models" in values:
        update_fields["enabled_models"] = normalize_enabled_models(
            list(values["enabled_models"] or []),
            require_model_type=True,
        )
    if "api_key" in values:
        if values["api_key"] is None:
            raise ValueError("清除 API Key 请使用空字符串")
        update_fields["api_key"] = validate_api_key(values["api_key"])

    urls_changed = (
        ("base_url" in update_fields and update_fields["base_url"] != provider.base_url)
        or (
            "embedding_base_url" in update_fields
            and update_fields["embedding_base_url"] != (getattr(provider, "embedding_base_url", "") or "")
        )
        or (
            "rerank_base_url" in update_fields
            and update_fields["rerank_base_url"] != (getattr(provider, "rerank_base_url", "") or "")
        )
    )
    if urls_changed and resolve_provider_api_key(provider.api_key or "") and "api_key" not in update_fields:
        raise ValueError("更改服务地址后必须重新提供 API Key")

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


async def discover_models(db: AsyncSession, provider_id: str) -> list[str]:
    provider = await _get_model_provider(db, provider_id)
    draft = {
        "base_url": normalize_base_url(provider.base_url),
        "protocol": validate_protocol(provider.protocol),
        "api_key": provider.api_key or "",
        "extra_headers": dict(getattr(provider, "extra_headers", None) or {}),
    }
    return [model["model_id"] for model in await _discover_config_models(draft)]


async def test_model_connection(db: AsyncSession, model_ref: str) -> dict[str, Any]:
    spec = await _resolve(db, model_ref, require_enabled=False)
    started = perf_counter()
    try:
        if spec.category == "chat":
            chat = build_chat_model(
                protocol=spec.protocol,
                model_id=spec.model_id,
                api_key=spec.api_key,
                base_url=spec.base_url,
                extra_headers=spec.extra_headers,
            )
            response = await chat.ainvoke("Reply with OK.")
            content = getattr(response, "content", None)
            tool_calls = getattr(response, "tool_calls", None)
            has_content = isinstance(content, str) or (isinstance(content, list) and bool(content))
            if not has_content and not (isinstance(tool_calls, list) and bool(tool_calls)):
                raise ModelConnectionError("invalid_response")
        elif spec.category == "embedding":
            embedder = build_embedding_model(
                protocol=spec.protocol,
                model_id=spec.model_id,
                api_key=spec.api_key,
                base_url=spec.embedding_base_url or spec.base_url,
                extra_headers=spec.extra_headers,
                batch_size=1,
                request_timeout=15.0,
            )
            vector = await embedder.aembed_query("OK")
            if not vector:
                raise ModelConnectionError("invalid_response")
        else:
            endpoint = spec.rerank_base_url or None
            if endpoint is None and spec.provider_id == "dashscope" and sys_config.dashscope_rerank_url.strip():
                endpoint = sys_config.dashscope_rerank_url.strip()
            reranker = build_reranker(
                protocol=spec.protocol,
                model_id=spec.model_id,
                api_key=spec.api_key,
                base_url=spec.base_url,
                endpoint=endpoint,
                extra_headers=spec.extra_headers,
                request_timeout=15.0,
            )
            results = await reranker.arerank(
                "OK",
                [RerankDocument(id="probe", text="OK", original_rank=1)],
                top_n=1,
            )
            if not results:
                raise ModelConnectionError("invalid_response")
    except ModelConnectionError as exc:
        return {
            "success": False,
            "elapsed_ms": (perf_counter() - started) * 1000,
            "error": exc.code,
            "status_code": exc.status_code,
        }
    except (EmbeddingError, RerankError) as exc:
        return {
            "success": False,
            "elapsed_ms": (perf_counter() - started) * 1000,
            "error": exc.code,
            "status_code": exc.status_code,
        }
    except httpx.TimeoutException:
        return {
            "success": False,
            "elapsed_ms": (perf_counter() - started) * 1000,
            "error": "timeout",
            "status_code": None,
        }
    except httpx.HTTPStatusError as exc:
        return {
            "success": False,
            "elapsed_ms": (perf_counter() - started) * 1000,
            "error": "http_error",
            "status_code": exc.response.status_code,
        }
    except httpx.RequestError:
        return {
            "success": False,
            "elapsed_ms": (perf_counter() - started) * 1000,
            "error": "connection_error",
            "status_code": None,
        }
    except ValueError:
        return {
            "success": False,
            "elapsed_ms": (perf_counter() - started) * 1000,
            "error": "invalid_response",
            "status_code": None,
        }
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        if isinstance(status_code, int):
            code = "http_error"
        elif isinstance(exc, TimeoutError):
            code = "timeout"
        else:
            code = "connection_error"
        return {
            "success": False,
            "elapsed_ms": (perf_counter() - started) * 1000,
            "error": code,
            "status_code": status_code if isinstance(status_code, int) else None,
        }
    return {
        "success": True,
        "elapsed_ms": (perf_counter() - started) * 1000,
        "error": None,
        "status_code": None,
    }


async def _settings_draft(
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
) -> dict[str, Any]:
    provider = await _get_model_provider(db, provider_id)
    normalized_base = normalize_base_url(base_url)
    normalized_embedding = normalize_optional_url(embedding_base_url)
    normalized_rerank = normalize_optional_url(rerank_base_url)
    if not isinstance(is_enabled, bool):
        raise ValueError("is_enabled 必须是布尔值")
    if api_key_provided:
        if api_key is None:
            raise ValueError("API Key 不可为 null")
        validated_key = validate_api_key(api_key)
    else:
        validated_key = provider.api_key or ""

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

    previous_models = normalize_enabled_models(
        list(getattr(provider, "enabled_models", None) or []),
        require_model_type=True,
        strip_legacy=True,
    )
    previous = {item["model_id"]: item for item in previous_models}
    model_types = {model["model_type"] for model in previous.values()}
    if not model_types:
        model_types = {
            model.model_type
            for preset in MODEL_PROVIDER_PRESETS
            if preset.provider_id == provider_id
            for model in preset.enabled_models
        }

    requested_models = normalize_enabled_models(models)
    enabled_models: list[dict[str, Any]] = []
    for item in requested_models:
        existing = previous.get(item["model_id"])
        if existing is None and len(model_types) != 1:
            raise ValueError("新增模型需要明确模型类型")
        merged = {
            "model_id": item["model_id"],
            "category": item["category"] if "category" in item else (existing["category"] if existing is not None else "chat"),
            "model_type": existing["model_type"] if existing is not None else next(iter(model_types)),
            "capabilities": item["capabilities"],
        }
        enabled_models.append(merged)

    return {
        "provider_id": provider_id,
        "name": provider.name,
        "protocol": validate_protocol(provider.protocol),
        "base_url": normalized_base,
        "embedding_base_url": normalized_embedding,
        "rerank_base_url": normalized_rerank,
        "extra_headers": extra_headers,
        "is_enabled": is_enabled,
        "enabled_models": enabled_models,
        "api_key": validated_key,
        "api_key_provided": api_key_provided,
    }


async def save_model_settings(
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
) -> dict[str, Any]:
    draft = await _settings_draft(
        db,
        provider_id,
        base_url=base_url,
        embedding_base_url=embedding_base_url,
        rerank_base_url=rerank_base_url,
        is_enabled=is_enabled,
        models=models,
        api_key=api_key,
        api_key_provided=api_key_provided,
    )
    update_fields: dict[str, Any] = {
        "base_url": draft["base_url"],
        "embedding_base_url": draft["embedding_base_url"],
        "rerank_base_url": draft["rerank_base_url"],
        "extra_headers": draft["extra_headers"],
        "is_enabled": draft["is_enabled"],
        "enabled_models": draft["enabled_models"],
    }
    if draft["api_key_provided"]:
        update_fields["api_key"] = draft["api_key"]
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


async def discover_settings_models(
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
) -> list[dict[str, Any]]:
    draft = await _settings_draft(
        db,
        provider_id,
        base_url=base_url,
        embedding_base_url=embedding_base_url,
        rerank_base_url=rerank_base_url,
        is_enabled=is_enabled,
        models=models,
        api_key=api_key,
        api_key_provided=api_key_provided,
    )
    return await _discover_config_models(draft)


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


async def test_settings_connection(
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
) -> dict[str, Any]:
    draft = await _settings_draft(
        db,
        provider_id,
        base_url=base_url,
        embedding_base_url=embedding_base_url,
        rerank_base_url=rerank_base_url,
        is_enabled=is_enabled,
        models=models,
        api_key=api_key,
        api_key_provided=api_key_provided,
    )
    started = perf_counter()
    try:
        await _discover_config_models(draft)
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
