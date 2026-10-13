from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.entities.sandbox import (
    SandboxFileContentResponse,
    SandboxFileOperationResponse,
    SandboxFileRenameRequest,
    SandboxFileUpdateRequest,
    SandboxWorkspaceResponse,
)
from server.service import sandbox_service
from server.utils.auth import AuthenticatedUser
from src.database import get_db

router = APIRouter(prefix="/sandbox", tags=["sandbox"])


def _raise_sandbox_http_error(exc: Exception) -> None:
    if isinstance(exc, FileExistsError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if isinstance(exc, (LookupError, FileNotFoundError)):
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
    editable: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> SandboxFileContentResponse:
    try:
        return await sandbox_service.read_workspace_file(
            db,
            uid=current_user.uid,
            thread_id=thread_id,
            path=path,
            editable=editable,
        )
    except (LookupError, ValueError, RuntimeError, OSError) as exc:
        _raise_sandbox_http_error(exc)


@router.post("/workspace/rename", response_model=SandboxFileOperationResponse)
async def rename_workspace_file(
    request: SandboxFileRenameRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
) -> SandboxFileOperationResponse:
    try:
        path = await sandbox_service.mutate_workspace_file(
            db, uid=current_user.uid, operation="rename", **request.model_dump(),
        )
        return SandboxFileOperationResponse(path=path)
    except (LookupError, ValueError, RuntimeError, OSError) as exc:
        _raise_sandbox_http_error(exc)


@router.put("/workspace/content", status_code=status.HTTP_204_NO_CONTENT)
async def update_workspace_file(
    request: SandboxFileUpdateRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        await sandbox_service.mutate_workspace_file(
            db, uid=current_user.uid, operation="write", **request.model_dump(),
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except (LookupError, ValueError, RuntimeError, OSError) as exc:
        _raise_sandbox_http_error(exc)


@router.delete("/workspace/file", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace_file(
    current_user: AuthenticatedUser,
    thread_id: str = Query(min_length=1),
    path: str = Query(min_length=1, max_length=4096),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        await sandbox_service.mutate_workspace_file(
            db, uid=current_user.uid, thread_id=thread_id, path=path, operation="delete",
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except (LookupError, ValueError, RuntimeError, OSError) as exc:
        _raise_sandbox_http_error(exc)
