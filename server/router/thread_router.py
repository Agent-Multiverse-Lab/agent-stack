from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from server.entities.agent import AgentSummary
from server.entities.thread import (
    ThreadDetailResponse,
    ThreadListResponse,
    ThreadRequest,
    ThreadResponse,
    ThreadSummaryResponse,
    ThreadUpdateRequest,
    UploadedAttachmentResponse,
)
from server.service import thread_service
from server.service.attachment_service import (
    AttachmentUpload,
    upload_attachments,
)
from server.utils.auth import AuthenticatedUser
from src.agents import agent_manager
from src.database import get_db

router = APIRouter(prefix="/chat", tags=["chat会话"])

MAX_FILES_PER_REQUEST = 10
MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_DOCUMENT_SIZE = 25 * 1024 * 1024

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/bmp",
    "image/svg+xml",
}
ALLOWED_DOCUMENT_TYPES = {
    "application/pdf",
    "application/csv",
    "application/msword",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/xhtml+xml",
    "text/plain",
    "text/html",
    "text/markdown",
    "text/csv",
    "application/json",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".bmp",
    ".svg",
}
ALLOWED_DOCUMENT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".docx",
    ".html",
    ".htm",
    ".json",
    ".csv",
    ".xls",
    ".xlsx",
    ".pdf",
    ".pptx",
}


@router.post("/thread", response_model=ThreadResponse)
async def create_thread(
    thread: ThreadRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
) -> ThreadResponse:
    """创建当前用户的顶层对话。"""
    try:
        conversation = await thread_service.create_thread(
            db,
            uid=current_user.uid,
            agent_id=thread.agent_id,
            title=thread.title,
            summary=thread.summary,
            metadata=thread.metadata,
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

    return ThreadResponse(
        thread_id=str(conversation.thread_id),
        uid=str(conversation.uid),
        agent_id=str(conversation.agent_id),
        title=str(conversation.title),
        metadata=dict(conversation.conversation_metadata or {}),
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@router.get("/thread", response_model=ThreadListResponse)
async def list_threads(
    current_user: AuthenticatedUser,
    limit: int = 20,
    cursor: str | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> ThreadListResponse:
    """分页列出或搜索当前用户的顶层对话。"""
    try:
        result = await thread_service.list_threads(
            db,
            uid=current_user.uid,
            limit=limit,
            cursor=cursor,
            query=q,
        )
        return ThreadListResponse(**result)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get("/thread/{thread_id}", response_model=ThreadDetailResponse)
async def get_thread_detail(
    thread_id: str,
    current_user: AuthenticatedUser,
    message_limit: int = 100,
    before_message_id: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> ThreadDetailResponse:
    """加载指定对话及一页持久化消息。"""
    try:
        result = await thread_service.get_thread_detail(
            db,
            uid=current_user.uid,
            thread_id=thread_id,
            message_limit=message_limit,
            before_message_id=before_message_id,
        )
        return ThreadDetailResponse(**result)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.patch("/thread/{thread_id}", response_model=ThreadSummaryResponse)
async def update_thread(
    thread_id: str,
    payload: ThreadUpdateRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
) -> ThreadSummaryResponse:
    """更新指定对话的标题、摘要或用户元数据。"""
    try:
        result = await thread_service.update_thread(
            db,
            uid=current_user.uid,
            thread_id=thread_id,
            fields=set(payload.model_fields_set),
            title=payload.title,
            summary=payload.summary,
            metadata=payload.metadata,
        )
        return ThreadSummaryResponse(**result)
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
    "/thread/{thread_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_thread(
    thread_id: str,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """软删除指定顶层对话及其内部子对话。"""
    try:
        await thread_service.delete_thread(
            db,
            uid=current_user.uid,
            thread_id=thread_id,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except thread_service.ThreadConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/agents", response_model=list[AgentSummary])
async def list_agent_summaries(
    current_user: AuthenticatedUser,
) -> list[AgentSummary]:
    """列出当前公开顶层 Agent。"""
    return [
        AgentSummary(**agent)
        for agent in agent_manager.list_top_level_agents()
    ]


@router.post(
    "/attachment/upload",
    response_model=list[UploadedAttachmentResponse],
)
async def upload_chat_attachments(
    current_user: AuthenticatedUser,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
) -> list[UploadedAttachmentResponse]:
    """上传用户附件，不触发对话。"""
    return await _upload_attachments(
        db=db,
        files=files,
        current_user=current_user,
    )


def _file_extension(filename: str | None) -> str:
    """获取文件后缀名。"""
    return Path(filename or "").suffix.lower()


def _is_allowed_file(
    *,
    filename: str | None,
    content_type: str,
    allowed_types: set[str],
    allowed_extensions: set[str],
) -> bool:
    """校验文件类型或后缀是否允许。"""
    extension = _file_extension(filename)
    return content_type in allowed_types or extension in allowed_extensions


async def _upload_attachments(
    *,
    db: AsyncSession,
    files: list[UploadFile],
    current_user: AuthenticatedUser,
) -> list[UploadedAttachmentResponse]:
    """校验上传内容，并把存储编排交给附件 Service。"""
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="至少需要上传一个文件。",
        )
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"单次上传文件数量不能超过 {MAX_FILES_PER_REQUEST} 个。",
        )

    uploads: list[AttachmentUpload] = []
    for upload in files:
        content_type = (
            upload.content_type or "application/octet-stream"
        ).lower()
        if _is_allowed_file(
            filename=upload.filename,
            content_type=content_type,
            allowed_types=ALLOWED_IMAGE_TYPES,
            allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
        ):
            max_file_size = MAX_IMAGE_SIZE
        elif _is_allowed_file(
            filename=upload.filename,
            content_type=content_type,
            allowed_types=ALLOWED_DOCUMENT_TYPES,
            allowed_extensions=ALLOWED_DOCUMENT_EXTENSIONS,
        ):
            max_file_size = MAX_DOCUMENT_SIZE
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "不支持的附件文件类型: "
                    f"{upload.filename or '未知'}."
                ),
            )

        content = await upload.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"文件 '{upload.filename or '未知'}' 内容为空。",
            )
        if len(content) > max_file_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"文件 '{upload.filename or '未知'}' 大小超过限制。",
            )

        uploads.append(
            AttachmentUpload(
                file_name=upload.filename or "file",
                content_type=content_type,
                content=content,
            )
        )

    responses = await upload_attachments(
        db,
        user_id=int(current_user.id),
        uploads=uploads,
    )
    return [
        UploadedAttachmentResponse(**response)
        for response in responses
    ]
