from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Attachment
from src.database.repositories import AttachmentRepository
from src.storage.minio import ATTACHMENT_BUCKET_NAME, get_storage
from src.utils import logger


@dataclass(frozen=True, slots=True)
class AttachmentUpload:
    """一个已经通过 HTTP 校验、等待上传的附件。"""

    file_name: str
    content_type: str
    content: bytes


def build_attachment_object_name(file_id: str) -> str:
    """构建尚未归入 Thread 的附件对象名。"""
    return f"save/attachments/{file_id}"


def build_thread_attachment_object_name(thread_id: str, file_id: str) -> str:
    """构建 Thread 级附件对象名。"""
    return f"save/{thread_id}/attachments/{file_id}"


async def upload_attachments(
    db: AsyncSession,
    *,
    user_id: int | str,
    uploads: Sequence[AttachmentUpload],
) -> list[dict[str, object]]:
    """上传对象并创建正式 Attachment 记录。"""
    storage = get_storage()
    repository = AttachmentRepository(db)
    uploaded_object_names: list[str] = []
    responses: list[dict[str, object]] = []

    try:
        for upload in uploads:
            file_id = str(uuid4())
            object_name = build_attachment_object_name(file_id)
            await storage.aupload_file(
                ATTACHMENT_BUCKET_NAME,
                object_name,
                upload.content,
                upload.content_type,
            )
            uploaded_object_names.append(object_name)

            attachment = await repository.create_attachment(
                file_id=file_id,
                user_id=user_id,
                file_name=upload.file_name,
                content_type=upload.content_type,
                file_size=len(upload.content),
                object_name=object_name,
            )
            access_url = await storage.create_file_access_url(
                ATTACHMENT_BUCKET_NAME,
                object_name,
            )
            responses.append(
                {
                    "file_id": str(attachment.file_id),
                    "file_name": upload.file_name,
                    "content_type": upload.content_type,
                    "file_size": len(upload.content),
                    "bucket_name": ATTACHMENT_BUCKET_NAME,
                    "object_name": object_name,
                    "access_url": access_url,
                }
            )

        await db.commit()
        return responses
    except Exception:
        await db.rollback()
        await _delete_objects(uploaded_object_names)
        logger.exception("附件上传失败：user_id=%s", user_id)
        raise


def attachment_file_ids(msg_metadata: dict[str, Any]) -> list[str]:
    """校验并按首次出现顺序返回附件 UUID4。"""
    values = msg_metadata.get("attachment_file_ids", [])
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError("msg_metadata.attachment_file_ids 必须是列表")

    file_ids: list[str] = []
    seen: set[str] = set()
    for value in values:
        try:
            parsed = UUID(value) if isinstance(value, str) else None
        except ValueError as exc:
            raise ValueError("attachment_file_ids 必须是 UUID4") from exc
        if parsed is None or parsed.version != 4:
            raise ValueError("attachment_file_ids 必须是 UUID4")

        file_id = str(parsed)
        if file_id not in seen:
            seen.add(file_id)
            file_ids.append(file_id)
    return file_ids


async def prepare_message_attachments(
    db: AsyncSession,
    *,
    user_id: int | str,
    thread_id: str,
    file_ids: Sequence[str],
) -> tuple[list[Attachment], list[tuple[str, str]]]:
    """校验附件归属，并复制仍在暂存位置的对象。"""
    if not file_ids:
        return [], []

    repository = AttachmentRepository(db)
    rows = await repository.list_by_file_ids_for_user(
        file_ids=file_ids,
        user_id=user_id,
    )
    attachments_by_file_id = {
        str(attachment.file_id): attachment for attachment in rows
    }
    if len(attachments_by_file_id) != len(file_ids):
        raise LookupError("附件不存在、已删除或不属于当前用户")

    attachments = [attachments_by_file_id[file_id] for file_id in file_ids]
    copied_objects: list[tuple[str, str]] = []
    storage = get_storage()
    try:
        for attachment in attachments:
            source_object_name = str(attachment.object_name)
            pending_object_name = build_attachment_object_name(
                str(attachment.file_id)
            )
            if source_object_name != pending_object_name:
                continue

            target_object_name = build_thread_attachment_object_name(
                thread_id,
                str(attachment.file_id),
            )
            await storage.acopy_file(
                ATTACHMENT_BUCKET_NAME,
                source_object_name,
                target_object_name,
            )
            copied_objects.append((source_object_name, target_object_name))
            await repository.update_object_name(
                attachment,
                object_name=target_object_name,
            )
    except Exception:
        await delete_copied_targets(copied_objects)
        raise

    return attachments, copied_objects


async def delete_copied_sources(
    copied_objects: Sequence[tuple[str, str]],
) -> None:
    """数据库提交后删除已经迁移成功的源对象。"""
    await _delete_objects([source for source, _ in copied_objects])


async def delete_copied_targets(
    copied_objects: Sequence[tuple[str, str]],
) -> None:
    """数据库回滚时删除新复制的目标对象。"""
    await _delete_objects([target for _, target in copied_objects])


async def _delete_objects(object_names: Sequence[str]) -> None:
    storage = get_storage()
    for object_name in object_names:
        try:
            await storage.adelete_file(ATTACHMENT_BUCKET_NAME, object_name)
        except Exception:
            logger.exception(
                "附件对象清理失败：bucket_name=%s object_name=%s",
                ATTACHMENT_BUCKET_NAME,
                object_name,
            )
