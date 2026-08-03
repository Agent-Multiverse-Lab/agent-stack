from pathlib import Path
from time import perf_counter

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
from server.service.thread_service import (
    ThreadConflictError,
    ThreadService,
    build_tmp_attachment_file_key,
)
from server.utils.auth import AuthenticatedUser
from src.agents import agent_manager
from src.database import get_db
from src.database.repositories import AttachmentRepository
from src.storage import get_storage
from src.utils import logger

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
        conversation = await ThreadService(db).create_thread(
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
        result = await ThreadService(db).list_threads(
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
        result = await ThreadService(db).get_thread_detail(
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
        result = await ThreadService(db).update_thread(
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
        await ThreadService(db).delete_thread(
            uid=current_user.uid,
            thread_id=thread_id,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ThreadConflictError as exc:
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
    "/attachment/tmp/upload",
    response_model=list[UploadedAttachmentResponse],
)
async def upload_tmp_attachments(
    current_user: AuthenticatedUser,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
) -> list[UploadedAttachmentResponse]:
    """附件上传到临时路径，不触发对话。"""
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
    """校验并上传当前用户的临时附件。"""
    logger.info(
        "收到上传请求: 用户ID=%s, 文件数量=%s, 类型=tmp_attachment.",
        current_user.id,
        len(files),
    )

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

    uploaded_keys: list[str] = []
    responses: list[UploadedAttachmentResponse] = []
    repository = AttachmentRepository(db)

    try:
        for upload in files:
            content_type = (upload.content_type or "").lower()
            if _is_allowed_file(
                filename=upload.filename,
                content_type=content_type,
                allowed_types=ALLOWED_IMAGE_TYPES,
                allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
            ):
                category = "image"
                max_file_size = MAX_IMAGE_SIZE
            elif _is_allowed_file(
                filename=upload.filename,
                content_type=content_type,
                allowed_types=ALLOWED_DOCUMENT_TYPES,
                allowed_extensions=ALLOWED_DOCUMENT_EXTENSIONS,
            ):
                category = "document"
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

            original_filename = upload.filename or "file"
            file_key = build_tmp_attachment_file_key(
                current_user.id,
                original_filename,
            )
            upload_started_at = perf_counter()
            await get_storage().upload_file(
                "knowledgebases",
                file_key,
                content,
                content_type or "application/octet-stream",
            )
            upload_duration_ms = (
                perf_counter() - upload_started_at
            ) * 1000
            logger.info(
                "附件上传到 tmp 完成: 用户ID=%s, 文件名=%s, "
                "file_key=%s, 文件大小=%s, 耗时=%.2fms.",
                current_user.id,
                original_filename,
                file_key,
                len(content),
                upload_duration_ms,
            )
            uploaded_keys.append(file_key)
            attachment = await repository.create_pending(
                user_id=current_user.id,
                attachment_name=original_filename,
                attachment_type=(
                    content_type or "application/octet-stream"
                ),
                attachment_size=len(content),
                attachment_path=file_key,
            )
            access_url = await get_storage().create_file_access_url(
                "knowledgebases",
                file_key,
            )

            responses.append(
                UploadedAttachmentResponse(
                    id=str(attachment.id),
                    file_name=original_filename,
                    content_type=(
                        content_type or "application/octet-stream"
                    ),
                    file_size=len(content),
                    file_key=file_key,
                    category=category,
                    access_url=access_url,
                    thumb_url=None,
                )
            )
        await db.commit()
    except Exception:
        await db.rollback()
        for file_key in uploaded_keys:
            try:
                await get_storage().delete_file("knowledgebases", file_key)
            except HTTPException:
                pass
        logger.exception(
            "上传失败，已尝试清理相关存储文件: "
            "用户ID=%s, 对话ID=%s, 类型=%s.",
            current_user.id,
            None,
            "tmp_attachment",
        )
        raise

    return responses
