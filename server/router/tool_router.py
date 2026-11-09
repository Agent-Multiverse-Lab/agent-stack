from fastapi import APIRouter

from server.entities.tool import ToolCatalogResponse, ToolOptionsResponse
from server.service.tool_service import list_tool_options, list_tools
from server.utils.auth import AuthenticatedUser

router = APIRouter(prefix="/system/tools", tags=["tools"])


@router.get("", response_model=ToolCatalogResponse)
async def get_tools(
    current_user: AuthenticatedUser,
    category: str | None = None,
) -> ToolCatalogResponse:
    return ToolCatalogResponse(data=list_tools(category))


@router.get("/options", response_model=ToolOptionsResponse)
async def get_tool_options(
    current_user: AuthenticatedUser,
) -> ToolOptionsResponse:
    return ToolOptionsResponse(data=list_tool_options())
