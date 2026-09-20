"""平台 Chat 模型管理、远程探测和内部连接参数解析。"""

from time import perf_counter
from typing import Any, get_args

import httpx
from pydantic import TypeAdapter
from redis.exceptions import RedisError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from server.entities.model import (
    ChatCapability,
    ConnectionTestResult,
    EnabledModel,
    ModelConnection,
    ModelProviderCreate,
    ModelProviderResponse,
    ModelProviderSummary,
    ModelProviderUpdate,
    ModelSettingsRequest,
    ModelSummary,
    ModelType,
    ProviderWriteResult,
    SettingsModel,
)
from server.service.model_outbound import UnsafeModelTarget, resolve_public_target
from src.database.models import ModelProvider
from src.database.repositories.model_repository import ModelRepository
from src.model import get_model_catalog
from src.model.model_cache import (
    get_provider_catalog_cache,
    invalidate_provider_catalog_cache,
    set_provider_catalog_cache,
)

_catalog_adapter = TypeAdapter(list[ModelSummary])
_CACHE_ERRORS = (RedisError, OSError, ValueError)


class ModelConnectionError(RuntimeError):
    """只暴露错误类别与状态码，避免上游响应或 URL 泄露凭据。"""

    def __init__(self, code: str, status_code: int | None = None):
        self.code = code
        self.status_code = status_code
        super().__init__(code)


async def list_models() -> dict[str, Any]:
    """保留现有 Chat 选择器的静态目录合同。"""
    return await get_model_catalog()


def _settings(provider: ModelProvider) -> ModelProviderCreate:
    return ModelProviderCreate.model_validate(provider, from_attributes=True)


def _public_provider(provider: ModelProvider) -> ModelProviderResponse:
    config = _settings(provider)
    return ModelProviderResponse(
        **config.model_dump(exclude={"api_key", "extra_headers"}),
        has_api_key=bool(config.api_key.get_secret_value()),
    )


async def _get_provider(db: AsyncSession, user_id: int, provider_id: str) -> ModelProvider:
    provider = await ModelRepository(db, user_id).get_provider_by_id(provider_id)
    if provider is None:
        raise LookupError("模型供应商不存在")
    return provider


async def get_provider(db: AsyncSession, user_id: int, provider_id: str) -> ModelProviderResponse:
    return _public_provider(await _get_provider(db, user_id, provider_id))


async def list_providers(db: AsyncSession, user_id: int) -> list[ModelProviderResponse]:
    return [_public_provider(provider) for provider in await ModelRepository(db, user_id).list_providers()]


async def list_provider_summaries(db: AsyncSession, user_id: int) -> list[ModelProviderSummary]:
    return [ModelProviderSummary(
        provider_id=provider.provider_id, name=provider.name,
        is_enabled=provider.is_enabled, has_api_key=bool(provider.api_key),
    ) for provider in await ModelRepository(db, user_id).list_providers()]


def _write_values(config: ModelProviderCreate | ModelProviderUpdate) -> dict[str, Any]:
    values = config.model_dump(exclude={"api_key", "extra_headers"})
    values["extra_headers"] = {name: value.get_secret_value() for name, value in config.extra_headers.items()}
    if config.api_key is not None:
        values["api_key"] = config.api_key.get_secret_value()
    return values


async def create_provider(
    db: AsyncSession, user_id: int,
    config: ModelProviderCreate,
) -> ProviderWriteResult:
    try:
        await ModelRepository(db, user_id).create_provider(**_write_values(config))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ValueError("供应商 ID 已存在") from None
    except SQLAlchemyError:
        await db.rollback()
        raise RuntimeError("保存模型供应商失败") from None
    return ProviderWriteResult(
        provider_id=config.provider_id,
        cache_refreshed=await rebuild_model_cache(db, user_id),
    )


async def update_provider(
    db: AsyncSession, user_id: int,
    provider_id: str,
    config: ModelProviderUpdate,
) -> ProviderWriteResult:
    try:
        provider = await _get_provider(db, user_id, provider_id)
        if config.base_url != provider.base_url and provider.api_key and config.api_key is None:
            raise ValueError("更改 Base URL 后必须重新提供 API Key")
        await ModelRepository(db, user_id).update_provider(provider, **_write_values(config))
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise RuntimeError("更新模型供应商失败") from None
    return ProviderWriteResult(
        provider_id=provider_id,
        cache_refreshed=await rebuild_model_cache(db, user_id),
    )


async def delete_provider(db: AsyncSession, user_id: int, provider_id: str) -> ProviderWriteResult:
    try:
        provider = await _get_provider(db, user_id, provider_id)
        await ModelRepository(db, user_id).delete_provider(provider)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise RuntimeError("删除模型供应商失败") from None
    return ProviderWriteResult(
        provider_id=provider_id,
        cache_refreshed=await rebuild_model_cache(db, user_id),
    )


async def _build_enabled_catalog(db: AsyncSession, user_id: int) -> list[ModelSummary]:
    catalog = []
    for provider in await ModelRepository(db, user_id).list_providers(enabled_only=True):
        config = _settings(provider)
        for model in config.enabled_models:
            catalog.append(
                ModelSummary(
                    id=f"{config.provider_id}:{model.model_id}",
                    provider_id=config.provider_id,
                    provider_name=config.name,
                    model_id=model.model_id,
                    model_type=model.model_type,
                )
            )
    return catalog


async def rebuild_model_cache(db: AsyncSession, user_id: int) -> bool:
    """提交后刷新目录；失败不回滚已提交的供应商配置。"""
    try:
        await invalidate_provider_catalog_cache(user_id)
        catalog = await _build_enabled_catalog(db, user_id)
        await set_provider_catalog_cache(user_id, [model.model_dump() for model in catalog])
        return True
    except _CACHE_ERRORS:
        return False
    except SQLAlchemyError:
        await db.rollback()  # 只结束提交后新开的读取事务。
        return False


async def list_enabled_models(db: AsyncSession, user_id: int) -> list[ModelSummary]:
    try:
        cached = await get_provider_catalog_cache(user_id)
        if cached is not None:
            return _catalog_adapter.validate_python(cached)
    except _CACHE_ERRORS:
        pass
    catalog = await _build_enabled_catalog(db, user_id)
    try:
        await set_provider_catalog_cache(user_id, [model.model_dump() for model in catalog])
    except _CACHE_ERRORS:
        pass
    return catalog


async def _resolve_connection(
    db: AsyncSession, user_id: int,
    model_ref: str,
    *,
    require_enabled: bool,
) -> ModelConnection:
    provider_id, separator, model_id = model_ref.partition(":")
    if not separator or not provider_id or not model_id:
        raise ValueError("模型引用必须为 provider_id:model_id")
    config = _settings(await _get_provider(db, user_id, provider_id))
    if require_enabled and not config.is_enabled:
        raise ValueError("模型供应商已停用")
    model = next((item for item in config.enabled_models if item.model_id == model_id), None)
    if model is None:
        raise LookupError("聊天模型未配置")
    return ModelConnection(
        provider_id=provider_id,
        model_id=model_id,
        model_type=model.model_type,
        protocol=config.protocol,
        base_url=config.base_url,
        api_key=config.api_key,
        extra_headers=config.extra_headers,
        body_overrides=model.body_overrides,
    )


async def resolve_runtime_model(db: AsyncSession, user_id: int, model_ref: str) -> ModelConnection:
    return await _resolve_connection(db, user_id, model_ref, require_enabled=True)


async def _request_json(
    base_url: str,
    headers: dict[str, str],
    path: str,
    *,
    body: dict[str, Any] | None = None,
) -> Any:
    try:
        target, authority, hostname = await resolve_public_target(base_url)
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False, trust_env=False) as client:
            response = await client.request(
                "GET" if body is None else "POST",
                f"{target}{path}",
                headers={**headers, "Host": authority},
                json=body,
                extensions={"sni_hostname": hostname},
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        raise ModelConnectionError("timeout") from None
    except httpx.HTTPStatusError as exc:
        raise ModelConnectionError("http_error", exc.response.status_code) from None
    except httpx.RequestError:
        raise ModelConnectionError("connection_error") from None
    except UnsafeModelTarget:
        raise ModelConnectionError("blocked_target") from None
    except ValueError:
        raise ModelConnectionError("invalid_response") from None
    except (OSError, TimeoutError):
        raise ModelConnectionError("connection_error") from None


def _explicit_non_chat(item: dict[str, Any]) -> bool:
    # /models 的用途元数据是可选扩展；未知用途保留为未验证候选。
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


async def discover_models(db: AsyncSession, user_id: int, provider_id: str) -> list[str]:
    config = _settings(await _get_provider(db, user_id, provider_id))
    return [model.model_id for model in await _discover_config_models(config)]


async def test_model_connection(db: AsyncSession, user_id: int, model_ref: str) -> ConnectionTestResult:
    connection = await _resolve_connection(db, user_id, model_ref, require_enabled=False)
    return await _test_connection(connection)


async def _test_connection(connection: ModelConnection) -> ConnectionTestResult:
    body: dict[str, Any] = {
        "max_tokens": 32,
        **connection.body_overrides,
        "model": connection.model_id,
        "messages": [{"role": "user", "content": "Reply with OK."}],
        "stream": False,
    }
    if "max_completion_tokens" in body:
        body.pop("max_tokens", None)
    started = perf_counter()
    try:
        payload = await _request_json(
            connection.base_url,
            connection.request_headers(),
            "/chat/completions",
            body=body,
        )
        choices = payload.get("choices") if isinstance(payload, dict) else None
        first = choices[0] if isinstance(choices, list) and choices else None
        message = first.get("message") if isinstance(first, dict) else None
        if (
            not isinstance(message, dict)
            or message.get("role") != "assistant"
            or not (
                isinstance(message.get("content"), str)
                or isinstance(message.get("content"), list)
                and bool(message["content"])
                or isinstance(message.get("reasoning_content"), str)
                or isinstance(message.get("tool_calls"), list)
                and bool(message["tool_calls"])
            )
        ):
            raise ModelConnectionError("invalid_response")
    except ModelConnectionError as exc:
        return ConnectionTestResult(
            success=False,
            elapsed_ms=(perf_counter() - started) * 1000,
            error=exc.code,
            status_code=exc.status_code,
        )
    return ConnectionTestResult(success=True, elapsed_ms=(perf_counter() - started) * 1000)


async def _settings_draft(
    db: AsyncSession, user_id: int, provider_id: str, request: ModelSettingsRequest,
) -> tuple[ModelProviderCreate, bool]:
    if provider_id not in get_args(ModelType):
        raise ValueError("不支持的模型供应商")
    provider = await ModelRepository(db, user_id).get_provider_by_id(provider_id)
    values = _settings(provider).model_dump() if provider else {
        "provider_id": provider_id, "name": provider_id,
    }
    previous = {item["model_id"]: item for item in values.get("enabled_models", [])}
    if provider and request.base_url != provider.base_url:
        if provider.api_key and "api_key" not in request.model_fields_set:
            raise ValueError("更改 Base URL 后必须重新提供 API Key")
        values["extra_headers"] = {}
    values.update(request.model_dump(exclude={"models", "api_key"}))
    if "api_key" in request.model_fields_set:
        values["api_key"] = request.api_key
    values["enabled_models"] = [
        EnabledModel(
            model_id=item.model_id,
            model_type=previous.get(item.model_id, {}).get("model_type", provider_id),
            body_overrides=previous.get(item.model_id, {}).get("body_overrides", {}),
            capabilities=item.capabilities,
        )
        for item in request.models
    ]
    return ModelProviderCreate.model_validate(values), provider is not None


async def save_model_settings(
    db: AsyncSession, user_id: int, provider_id: str, request: ModelSettingsRequest,
) -> ProviderWriteResult:
    config, exists = await _settings_draft(db, user_id, provider_id, request)
    if exists:
        return await update_provider(
            db, user_id, provider_id,
            ModelProviderUpdate.model_validate(config.model_dump(exclude={"provider_id"})),
        )
    return await create_provider(db, user_id, config)


async def discover_settings_models(
    db: AsyncSession, user_id: int, provider_id: str, request: ModelSettingsRequest,
) -> list[SettingsModel]:
    config, _ = await _settings_draft(db, user_id, provider_id, request)
    return await _discover_config_models(config)


async def _discover_config_models(config: ModelProviderCreate) -> list[SettingsModel]:
    headers = {key: value.get_secret_value() for key, value in config.extra_headers.items()}
    if key := config.api_key.get_secret_value():
        headers["Authorization"] = f"Bearer {key}"
    payload = await _request_json(config.base_url, headers, "/models")
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ModelConnectionError("invalid_response")
    models: dict[str, SettingsModel] = {}
    for item in payload["data"]:
        if not isinstance(item, dict):
            raise ModelConnectionError("invalid_response")
        model_id = item.get("id")
        if not isinstance(model_id, str) or not model_id:
            raise ModelConnectionError("invalid_response")
        try:
            EnabledModel.validate_model_id(model_id)
        except ValueError:
            raise ModelConnectionError("invalid_response") from None
        if _explicit_non_chat(item):
            continue
        metadata = item.get("capabilities", [])
        if isinstance(metadata, dict):
            metadata = [key for key, value in metadata.items() if value is True]
        labels = set(value for value in metadata if isinstance(value, str)) if isinstance(metadata, list) else set()
        capabilities = [label for label in get_args(ChatCapability) if label in labels]
        models[model_id] = SettingsModel(model_id=model_id, capabilities=capabilities)
    return [models[key] for key in sorted(models)]


async def test_settings_connection(
    db: AsyncSession, user_id: int, provider_id: str, request: ModelSettingsRequest,
) -> ConnectionTestResult:
    config, _ = await _settings_draft(db, user_id, provider_id, request)
    started = perf_counter()
    try:
        await _discover_config_models(config)
    except ModelConnectionError as exc:
        return ConnectionTestResult(
            success=False,
            elapsed_ms=(perf_counter() - started) * 1000,
            error=exc.code,
            status_code=exc.status_code,
        )
    return ConnectionTestResult(success=True, elapsed_ms=(perf_counter() - started) * 1000)
