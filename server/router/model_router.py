from fastapi import APIRouter, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession

from server.entities.model import ModelApiResponse, ModelProvider, ProviderModelCatalog
from server.utils.auth import AuthenticatedUser
from src.database import get_db
from src.model.service import (
    ModelConnectionError,
    ModelProviderConflictError,
    create_model_provider,
    delete_model_provider,
    discover_provider_models,
    get_model_provider,
    list_model_providers,
    list_models,
    test_provider_connection,
    update_model_provider,
)
from src.model.utils import ModelCategory


class ModelSettingsRoute(APIRoute):
    """校验错误不回传含密钥的原始输入。"""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request):
            try:
                return await handler(request)
            except RequestValidationError:
                raise HTTPException(422, "模型配置格式无效") from None
            except ModelConnectionError as exc:
                raise HTTPException(502, f"模型服务请求失败：{exc.code}") from None
            except LookupError:
                raise HTTPException(404, "模型供应商不存在") from None
            except ModelProviderConflictError:
                raise HTTPException(409, "模型供应商已存在") from None
            except ValueError:
                raise HTTPException(422, "模型配置无效，请检查地址、密钥和聊天模型选择") from None
            except RuntimeError:
                raise HTTPException(500, "保存模型配置失败") from None

        return handle


router = APIRouter(prefix="/models", tags=["models"], route_class=ModelSettingsRoute)


@router.get("", response_model=ModelApiResponse[dict[str, ProviderModelCatalog]])
async def get_models(
    current_user: AuthenticatedUser,
    category: ModelCategory = "chat",
    db: AsyncSession = Depends(get_db),
):
    return {
        "status": "success",
        "data": await list_models(db, category=category),
    }


settings_router = APIRouter(prefix="/providers", route_class=ModelSettingsRoute)


@settings_router.get("", response_model=ModelApiResponse[list[ModelProvider]])
async def list_providers(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return {
        "status": "success",
        "data": await list_model_providers(db),
    }


@settings_router.post("", status_code=201)
async def create_provider(payload: ModelProvider, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return {
        "status": "success",
        "data": await create_model_provider(
            db,
            provider_id=payload.provider_id,
            name=payload.name,
            protocol=payload.protocol,
            base_url=payload.base_url,
            embedding_base_url=payload.embedding_base_url,
            rerank_base_url=payload.rerank_base_url,
            is_enabled=payload.is_enabled,
            models=payload.models,
            api_key=payload.api_key if "api_key" in payload.model_fields_set else "",
        ),
    }


@settings_router.get("/{provider_id}", response_model=ModelApiResponse[ModelProvider])
async def get_provider(
    provider_id: str,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return {
        "status": "success",
        "data": await get_model_provider(db, provider_id),
    }


@settings_router.put("/{provider_id}")
@settings_router.post("/{provider_id}")
async def update_provider(provider_id: str, payload: ModelProvider, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return {
        "status": "success",
        "data": await update_model_provider(
            db,
            provider_id,
            base_url=payload.base_url,
            embedding_base_url=payload.embedding_base_url,
            rerank_base_url=payload.rerank_base_url,
            is_enabled=payload.is_enabled,
            models=payload.models,
            api_key=payload.api_key,
            api_key_provided="api_key" in payload.model_fields_set,
            name=payload.name if "name" in payload.model_fields_set else None,
            protocol=payload.protocol if "protocol" in payload.model_fields_set else None,
        ),
    }


@settings_router.delete("/{provider_id}")
async def delete_provider(provider_id: str, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return {
        "status": "success",
        "data": await delete_model_provider(db, provider_id),
    }


@settings_router.post("/{provider_id}/discover")
async def discover_provider(provider_id: str, payload: ModelProvider, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return {
        "status": "success",
        "data": await discover_provider_models(
            db,
            provider_id,
            base_url=payload.base_url,
            api_key=payload.api_key,
            api_key_provided="api_key" in payload.model_fields_set,
            protocol=payload.protocol if "protocol" in payload.model_fields_set else None,
        ),
    }


@settings_router.post("/{provider_id}/test")
async def test_provider(provider_id: str, payload: ModelProvider, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return {
        "status": "success",
        "data": await test_provider_connection(
            db,
            provider_id,
            base_url=payload.base_url,
            api_key=payload.api_key,
            api_key_provided="api_key" in payload.model_fields_set,
            protocol=payload.protocol if "protocol" in payload.model_fields_set else None,
        ),
    }


router.include_router(settings_router)
