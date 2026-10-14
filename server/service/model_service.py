"""平台 Chat 模型管理、远程探测和内部连接参数解析。"""

from copy import deepcopy
from time import perf_counter
from typing import Any, get_args

import httpx
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
    ProviderWriteResult,
    SettingsModel,
)
from server.service.model_outbound import UnsafeModelTarget, resolve_public_target
from src.database.models import ModelProvider
from src.database.repositories.model_repository import ModelRepository
from src.model import get_model_catalog
from src.model.providers.builtin import MODEL_PROVIDER_PRESETS


class ModelConnectionError(RuntimeError):
    """只暴露错误类别与状态码，避免上游响应或 URL 泄露凭据。"""

    def __init__(self, code: str, status_code: int | None = None):
        self.code = code
        self.status_code = status_code
        super().__init__(code)


async def list_models() -> dict[str, Any]:
    """保留现有 Chat 选择器的静态目录合同。"""
    return await get_model_catalog()


async def ensure_builtin_model_providers(db: AsyncSession) -> None:
    """显式校验全部预置并补齐缺失行；接入 lifespan 时由调用方另行预热目录。"""
    pending: list[ModelProviderCreate] = []
    seen: set[str] = set()
    for preset in MODEL_PROVIDER_PRESETS:
        config = ModelProviderCreate.model_validate({
            "provider_id": preset.provider_id,
            "name": preset.name,
            "base_url": preset.base_url,
            "protocol": preset.protocol,
            "is_enabled": preset.is_enabled,
            "api_key": "",
            "extra_headers": {},
            "enabled_models": [
                {
                    "model_id": model.model_id,
                    "model_type": model.model_type,
                    "body_overrides": deepcopy(model.body_overrides),
                    "capabilities": list(model.capabilities),
                }
                for model in preset.enabled_models
            ],
        })
        if config.provider_id in seen:
            raise ValueError("预置供应商 ID 不得重复")
        if not config.enabled_models:
            raise ValueError("预置模型列表不能为空")
        seen.add(config.provider_id)
        pending.append(config)

    repository = ModelRepository(db)
    try:
        for config in pending:
            await repository.insert_provider_if_missing(**_write_values(config))
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise RuntimeError("补齐模型供应商失败") from None


def _settings(provider: ModelProvider) -> ModelProviderCreate:
    return ModelProviderCreate.model_validate(provider, from_attributes=True)


def _public_provider(provider: ModelProvider) -> ModelProviderResponse:
    config = _settings(provider)
    return ModelProviderResponse(
        **config.model_dump(exclude={"api_key", "extra_headers"}),
        has_api_key=bool(config.api_key.get_secret_value()),
    )


async def _get_provider(db: AsyncSession, provider_id: str) -> ModelProvider:
    provider = await ModelRepository(db).get_provider_by_id(provider_id)
    if provider is None:
        raise LookupError("模型供应商不存在")
    return provider


async def get_provider(db: AsyncSession, provider_id: str) -> ModelProviderResponse:
    return _public_provider(await _get_provider(db, provider_id))


async def list_providers(db: AsyncSession) -> list[ModelProviderResponse]:
    return [_public_provider(provider) for provider in await ModelRepository(db).list_providers()]


async def get_settings_provider(
    db: AsyncSession, provider_id: str,
) -> ModelProviderResponse:
    return await get_provider(db, provider_id)


async def list_settings_provider_summaries(
    db: AsyncSession,
) -> list[ModelProviderSummary]:
    return [
        ModelProviderSummary(
            provider_id=provider.provider_id,
            name=provider.name,
            is_enabled=provider.is_enabled,
            has_api_key=bool(provider.api_key),
        )
        for provider in await ModelRepository(db).list_providers()
    ]


def _write_values(config: ModelProviderCreate | ModelProviderUpdate) -> dict[str, Any]:
    values = config.model_dump(exclude={"api_key", "extra_headers"})
    values["extra_headers"] = {name: value.get_secret_value() for name, value in config.extra_headers.items()}
    if config.api_key is not None:
        values["api_key"] = config.api_key.get_secret_value()
    return values


async def create_provider(
    db: AsyncSession,
    config: ModelProviderCreate,
) -> ProviderWriteResult:
    try:
        await ModelRepository(db).create_provider(**_write_values(config))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ValueError("供应商 ID 已存在") from None
    except SQLAlchemyError:
        await db.rollback()
        raise RuntimeError("保存模型供应商失败") from None
    return ProviderWriteResult(
        provider_id=config.provider_id,
        cache_refreshed=False,
    )


async def update_provider(
    db: AsyncSession,
    provider_id: str,
    config: ModelProviderUpdate,
) -> ProviderWriteResult:
    try:
        provider = await _get_provider(db, provider_id)
        if config.base_url != provider.base_url and provider.api_key and config.api_key is None:
            raise ValueError("更改 Base URL 后必须重新提供 API Key")
        await ModelRepository(db).update_provider(provider, **_write_values(config))
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise RuntimeError("更新模型供应商失败") from None
    return ProviderWriteResult(
        provider_id=provider_id,
        cache_refreshed=False,
    )


async def delete_provider(db: AsyncSession, provider_id: str) -> ProviderWriteResult:
    try:
        provider = await _get_provider(db, provider_id)
        await ModelRepository(db).delete_provider(provider)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise RuntimeError("删除模型供应商失败") from None
    return ProviderWriteResult(
        provider_id=provider_id,
        cache_refreshed=False,
    )


async def list_enabled_models(db: AsyncSession) -> list[ModelSummary]:
    """读取全局已启用模型；公开 Redis 目录在接入阶段实现。"""
    catalog = []
    for provider in await ModelRepository(db).list_providers(enabled_only=True):
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


async def _resolve_connection(
    db: AsyncSession,
    model_ref: str,
    *,
    require_enabled: bool,
) -> ModelConnection:
    provider_id, separator, model_id = model_ref.partition(":")
    if not separator or not provider_id or not model_id:
        raise ValueError("模型引用必须为 provider_id:model_id")
    config = _settings(await _get_provider(db, provider_id))
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


async def resolve_runtime_model(db: AsyncSession, model_ref: str) -> ModelConnection:
    return await _resolve_connection(db, model_ref, require_enabled=True)


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


async def discover_models(db: AsyncSession, provider_id: str) -> list[str]:
    config = _settings(await _get_provider(db, provider_id))
    return [model.model_id for model in await _discover_config_models(config)]


async def test_model_connection(db: AsyncSession, model_ref: str) -> ConnectionTestResult:
    connection = await _resolve_connection(db, model_ref, require_enabled=False)
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
    db: AsyncSession, provider_id: str, request: ModelSettingsRequest,
) -> ModelProviderUpdate:
    provider = await _get_provider(db, provider_id)
    values = _settings(provider).model_dump(exclude={"provider_id"})
    previous = {item["model_id"]: item for item in values.get("enabled_models", [])}
    if request.base_url != provider.base_url:
        if provider.api_key and "api_key" not in request.model_fields_set:
            raise ValueError("更改 Base URL 后必须重新提供 API Key")
        values["extra_headers"] = {}
    values.update(request.model_dump(exclude={"models", "api_key"}))
    if "api_key" in request.model_fields_set:
        values["api_key"] = request.api_key
    model_types = {model["model_type"] for model in previous.values()}
    if not model_types:
        model_types = {
            model.model_type
            for preset in MODEL_PROVIDER_PRESETS if preset.provider_id == provider_id
            for model in preset.enabled_models
        }
    enabled_models = []
    for item in request.models:
        existing = previous.get(item.model_id)
        if existing is None and len(model_types) != 1:
            raise ValueError("新增模型需要明确模型类型，请使用完整供应商配置")
        enabled_models.append(EnabledModel(
            model_id=item.model_id,
            model_type=existing["model_type"] if existing is not None else next(iter(model_types)),
            body_overrides=deepcopy(existing["body_overrides"]) if existing is not None else {},
            capabilities=item.capabilities,
        ).model_dump())
    values["enabled_models"] = enabled_models
    return ModelProviderUpdate.model_validate(values)


async def save_model_settings(
    db: AsyncSession, provider_id: str, request: ModelSettingsRequest,
) -> ProviderWriteResult:
    config = await _settings_draft(db, provider_id, request)
    return await update_provider(db, provider_id, config)


async def discover_settings_models(
    db: AsyncSession, provider_id: str, request: ModelSettingsRequest,
) -> list[SettingsModel]:
    config = await _settings_draft(db, provider_id, request)
    return await _discover_config_models(config)


async def _discover_config_models(config: ModelProviderCreate | ModelProviderUpdate) -> list[SettingsModel]:
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
    db: AsyncSession, provider_id: str, request: ModelSettingsRequest,
) -> ConnectionTestResult:
    config = await _settings_draft(db, provider_id, request)
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
