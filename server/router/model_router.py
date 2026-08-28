from typing import Any

from fastapi import APIRouter

from server.service.model_service import list_models

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=dict[str, Any])
async def get_models():
    return await list_models()
