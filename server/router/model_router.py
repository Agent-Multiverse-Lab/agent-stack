from fastapi import APIRouter, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession

from server.entities.model import (
    ChatModelListResponse,
    ConnectionTestResult,
    ModelProviderResponse,
    ModelProviderSummary,
    ModelSettingsRequest,
    ProviderWriteResult,
    SettingsModel,
)
from server.service import model_service
from server.utils.auth import AuthenticatedUser
from src.database import get_db

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=ChatModelListResponse)
async def get_models(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    return await model_service.list_models(db)


class ModelSettingsRoute(APIRoute):
    """校验错误不回传含密钥的原始输入。"""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request):
            try:
                return await handler(request)
            except RequestValidationError:
                raise HTTPException(422, "模型配置格式无效") from None
            except model_service.ModelConnectionError as exc:
                raise HTTPException(502, f"模型服务请求失败：{exc.code}") from None
            except LookupError:
                raise HTTPException(404, "模型供应商不存在") from None
            except ValueError:
                raise HTTPException(422, "模型配置无效，请检查地址、密钥和聊天模型选择") from None
            except RuntimeError:
                raise HTTPException(500, "保存模型配置失败") from None

        return handle


settings_router = APIRouter(prefix="/providers", route_class=ModelSettingsRoute)


@settings_router.get("", response_model=list[ModelProviderSummary])
async def get_model_providers(current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return await model_service.list_settings_provider_summaries(db)


@settings_router.get("/{provider_id}", response_model=ModelProviderResponse)
async def get_model_provider(provider_id: str, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return await model_service.get_settings_provider(db, provider_id)


@settings_router.post("/{provider_id}", response_model=ProviderWriteResult)
async def save_model_provider(provider_id: str, payload: ModelSettingsRequest, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return await model_service.save_model_settings(db, provider_id, payload)


@settings_router.post("/{provider_id}/discover", response_model=list[SettingsModel])
async def discover_provider_models(provider_id: str, payload: ModelSettingsRequest, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return await model_service.discover_settings_models(db, provider_id, payload)


@settings_router.post("/{provider_id}/test", response_model=ConnectionTestResult)
async def test_provider_connection(provider_id: str, payload: ModelSettingsRequest, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return await model_service.test_settings_connection(db, provider_id, payload)


router.include_router(settings_router)
