from typing import Any

from src.model import get_model_catalog


async def list_models() -> dict[str, Any]:
    return await get_model_catalog()
