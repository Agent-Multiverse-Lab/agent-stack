import uuid
from pathlib import Path
from time import perf_counter
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.service.conversation_service import (
    build_tmp_attachment_file_key,
)
from server.utils.auth import AuthenticatedUser
from src.agents import agent_manager
from src.database import get_db
from src.database.models import User
from src.database.repositories import AgentRepository, AttachmentRepository, ConversationRepository
from src.storage import get_storage
from src.utils import logger

router = APIRouter(prefix="/chat", tags=["chat会话"])



class ThreadRequest(BaseModel):
    title: str | None = None
    # FIXME: 可空字段必须提供默认值，否则 Pydantic 仍会把它当成必填参数。
    summary: str | None = None
    agent_id: str
    metadata: dict | None = None
    
class ThreadResponse(BaseModel):
    uid: str
    title: str
    thread_id: str
    agent_id:str
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    
    

@router.post("/thread", response_model=ThreadResponse)
async def create_thread(
    thread: ThreadRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """ARQ实现异步的方式，首先创建对话空间， 然后创建thread之后，再当前会话创建agentrun事件，
        ARQ拿着id入队，redis执行生成任务。前端只需要拿事件id去队列消费就可以了，就是完全的解耦
    """
    user_result = await db.execute(select(User).where(User.uid == current_user.uid))
    # FIXME: Result 对象本身恒为真，必须检查实际查询出的 User。
    user = user_result.scalar_one_or_none()
    if user is None:
        logger.error(f"用户：{current_user.uid}，不存在")
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # OPTIMIZE
    agent_repo = AgentRepository(db)
    # FIXME: 创建顶层对话时显式按 father 类型解析 Agent。
    agent_result = await agent_repo.get_by_slug_for_run_type(
        slug=thread.agent_id,
        run_type="chat",
    )
    
    if not agent_result:
        logger.exception(f"智能体：{agent_result} 不存在")
        raise HTTPException(status_code=404, detail="智能体不存在")
    
    # FIXME: Conversation.title 不允许为空，原型阶段提供最小默认标题。
    title = thread.title or "新对话"
    summary = thread.summary
    
    thread_id = str(uuid.uuid4())
    agent_id = agent_result.slug
    thead_meatadata = thread.metadata or {}
    
    # 每个agent带有自己的可能配备自己的 虚拟文件系统，这个后续会做成单独的
    thead_meatadata["backend_id"] = agent_result.backend_id 
    
    
    conv_repo = ConversationRepository(db)
    conversation = await conv_repo.create_conversation(
        uid=current_user.uid,
        thread_id=thread_id,
        agent_slug=agent_id,
        title = title,
        summary=summary,
        conversation_metadata=thead_meatadata)
    
    # FIXME: 返回字段必须与 ThreadResponse.thread_id 对齐。
    return {
      "thread_id": conversation.thread_id,
      "uid": conversation.uid,
      "agent_id": conversation.agent_id,
      "title": conversation.title,
      "metadata": conversation.conversation_metadata or {},
      "created_at": conversation.created_at.isoformat(),
      "updated_at": conversation.updated_at.isoformat(),
  }


    
    
    
    

# 配置常量
MAX_FILES_PER_REQUEST = 10
MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_DOCUMENT_SIZE = 25 * 1024 * 1024

# 文件类型限制
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


class UploadedAttachmentResponse(BaseModel):
    """上传成功后的附件响应。"""

    id: str
    file_name: str
    content_type: str
    file_size: int
    file_key: str
    category: str
    access_url: str
    thumb_url: str | None = None
    parser: str | None = None
    parse_status: str | None = None
    parse_error: str | None = None
    parsed_text: str | None = None
    parse_metadata: dict[str, Any] = Field(default_factory=dict)


class AgentSummary(BaseModel):
    id: str
    name: str
    description: str


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


@router.get("/agents", response_model=list[AgentSummary])
async def list_agent_summaries(current_user: AuthenticatedUser):
    # FIXME: 公开列表只返回已由启动流程写入数据库的顶层 Agent。
    return [AgentSummary(**agent) for agent in agent_manager.list_top_level_agents()]


async def _upload_attachments(
    *,
    db: AsyncSession,
    files: list[UploadFile],
    current_user: AuthenticatedUser,
) -> list[UploadedAttachmentResponse]:
    """通用附件上传处理。"""
    logger.info(
        f"收到上传请求: 用户ID={current_user.id}, 文件数量={len(files)}, 类型=tmp_attachment."
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
                    detail=f"不支持的附件文件类型: {upload.filename or '未知'}.",
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
            upload_duration_ms = (perf_counter() - upload_started_at) * 1000
            logger.info(
                "附件上传到 tmp 完成: 用户ID=%s, 文件名=%s, file_key=%s, 文件大小=%s, 耗时=%.2fms.",
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
                attachment_type=content_type or "application/octet-stream",
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
                    content_type=content_type or "application/octet-stream",
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
        # 发生异常时回滚存储中的文件
        for file_key in uploaded_keys:
            try:
                await get_storage().delete_file("knowledgebases", file_key)
            except HTTPException:
                pass
        logger.exception(
            "上传失败，已尝试清理相关存储文件: 用户ID=%s, 对话ID=%s, 类型=%s.",
            current_user.id,
            None,
            "tmp_attachment",
        )
        raise

    return responses


@router.post(
    "/attachment/tmp/upload",
    response_model=list[UploadedAttachmentResponse],
)
async def upload_tmp_attachments(
    current_user: AuthenticatedUser,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    """附件上传到临时路径，不触发对话。"""
    return await _upload_attachments(
        db=db,
        files=files,
        current_user=current_user,
    )
