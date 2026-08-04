from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.repositories import AttachmentRepository
from src.storage.minio import (
    ATTACHMENT_BUCKET_NAME,
    get_storage,
    sanitize_filename,
)
from src.utils import logger


@dataclass(frozen=True, slots=True)
class PendingAttachmentUpload:
    """一个已经通过 HTTP 校验、等待落盘的附件。"""

    file_name: str
    content_type: str
    content: bytes
    category: str


def build_tmp_attachment_object_name(
    user_id: int | str,
    file_id: str,
    file_name: str,
) -> str:
    """使用外部文件 ID 生成临时对象名。"""
    return (
        f"tmp/{user_id}/chat/attachment/{file_id}/"
        f"{sanitize_filename(file_name)}"
    )


async def upload_pending_attachments(
    db: AsyncSession,
    *,
    user_id: int | str,
    uploads: Sequence[PendingAttachmentUpload],
) -> list[dict[str, object]]:
    """上传临时对象并创建使用同一 file_id 的 pending 记录。"""
    attachment_storage = get_storage()
    repository = AttachmentRepository(db)
    uploaded_object_names: list[str] = []
    responses: list[dict[str, object]] = []

    try:
        for upload in uploads:
            file_id = str(uuid4())
            object_name = build_tmp_attachment_object_name(
                user_id,
                file_id,
                upload.file_name,
            )
            await attachment_storage.aupload_file(
                ATTACHMENT_BUCKET_NAME,
                object_name,
                upload.content,
                upload.content_type,
            )
            uploaded_object_names.append(object_name)

            attachment = await repository.create_pending_attachment(
                file_id=file_id,
                user_id=user_id,
                attachment_name=upload.file_name,
                attachment_type=upload.content_type,
                attachment_size=len(upload.content),
                original_object_name=object_name,
            )
            access_url = await attachment_storage.create_file_access_url(
                ATTACHMENT_BUCKET_NAME,
                object_name,
            )
            responses.append(
                {
                    "id": str(attachment.file_id),
                    "file_name": upload.file_name,
                    "content_type": upload.content_type,
                    "file_size": len(upload.content),
                    "category": upload.category,
                    "status": "pending",
                    "access_url": access_url,
                }
            )

        await db.commit()
        return responses
    except Exception:
        await db.rollback()
        for object_name in uploaded_object_names:
            try:
                await attachment_storage.adelete_file(
                    ATTACHMENT_BUCKET_NAME,
                    object_name,
                )
            except Exception:
                logger.exception(
                    "附件上传回滚清理失败：user_id=%s object_name=%s",
                    user_id,
                    object_name,
                )
        logger.exception("附件临时上传失败：user_id=%s", user_id)
        raise
