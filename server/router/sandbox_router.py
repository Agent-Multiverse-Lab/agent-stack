from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.entities.sandbox import SandboxFileContentResponse, SandboxWorkspaceResponse
from server.service import sandbox_service
from server.utils.auth import AuthenticatedUser
from src.database import get_db

router = APIRouter(prefix="/sandbox", tags=["sandbox"])


def _raise_sandbox_http_error(exc: Exception) -> None:
    if isinstance(exc, LookupError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=str(exc),
    ) from exc


@router.get("/workspace", response_model=SandboxWorkspaceResponse)
async def list_workspace(
    current_user: AuthenticatedUser,
    thread_id: str = Query(min_length=1),
    path: str = Query(default="/workspace"),
    db: AsyncSession = Depends(get_db),
) -> SandboxWorkspaceResponse:
    try:
        return await sandbox_service.list_workspace(
            db,
            uid=current_user.uid,
            thread_id=thread_id,
            path=path,
        )
    except (LookupError, ValueError, RuntimeError) as exc:
        _raise_sandbox_http_error(exc)


@router.get("/workspace/content", response_model=SandboxFileContentResponse)
async def read_workspace_file(
    current_user: AuthenticatedUser,
    thread_id: str = Query(min_length=1),
    path: str = Query(min_length=1),
    db: AsyncSession = Depends(get_db),
) -> SandboxFileContentResponse:
    try:
        return await sandbox_service.read_workspace_file(
            db,
            uid=current_user.uid,
            thread_id=thread_id,
            path=path,
        )
    except (LookupError, ValueError, RuntimeError) as exc:
        _raise_sandbox_http_error(exc)
