"""用户上传附件的 Library API。"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.entities.library import (
    LibraryAttachmentItem,
    LibraryAttachmentListResponse,
    LibraryAttachmentRenameRequest,
)
from server.service.library_service import (
    delete_library_attachment,
    get_library_attachment,
    list_library_attachments,
    rename_library_attachment,
)
from server.utils.auth import AuthenticatedUser
from src.database import get_db

router = APIRouter(prefix="/libraries", tags=["libraries"])


@router.get("/attachments", response_model=LibraryAttachmentListResponse)
async def list_attachments(
    current_user: AuthenticatedUser,
    limit: int = 50,
    before_id: int | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """分页列出当前用户上传的附件。"""
    try:
        return await list_library_attachments(
            db,
            user_id=str(current_user.id),
            limit=limit,
            before_id=before_id,
            query=q,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/attachments/{attachment_id}",
    response_model=LibraryAttachmentItem,
)
async def get_attachment(
    attachment_id: str,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """读取当前用户的一个附件。"""
    try:
        return await get_library_attachment(
            db,
            user_id=str(current_user.id),
            attachment_id=attachment_id,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.patch(
    "/attachments/{attachment_id}",
    response_model=LibraryAttachmentItem,
)
async def rename_attachment(
    attachment_id: str,
    payload: LibraryAttachmentRenameRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """修改当前用户附件的展示文件名。"""
    try:
        return await rename_library_attachment(
            db,
            user_id=str(current_user.id),
            attachment_id=attachment_id,
            file_name=payload.file_name,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.delete(
    "/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_attachment(
    attachment_id: str,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """删除当前用户附件。"""
    try:
        await delete_library_attachment(
            db,
            user_id=str(current_user.id),
            attachment_id=attachment_id,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
