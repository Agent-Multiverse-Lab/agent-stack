"""用户附件 Library 用例。"""

from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Attachment
from src.database.repositories import AttachmentRepository
from src.storage.minio import ATTACHMENT_BUCKET_NAME, get_storage


async def list_library_attachments(
    db: AsyncSession,
    *,
    user_id: int | str,
    limit: int = 50,
    before_id: int | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    """分页列出当前用户正式且未删除的附件。"""
    if not 1 <= limit <= 100:
        raise ValueError("limit 必须在 1 到 100 之间")
    if before_id is not None and before_id <= 0:
        raise ValueError("before_id 必须是正整数")

    query_text = query.strip() if query is not None else None
    if query is not None and not query_text:
        raise ValueError("查询词不能为空")

    attachments = await AttachmentRepository(
        db
    ).list_library_attachments_for_user(
        user_id=user_id,
        limit=limit + 1,
        before_id=before_id,
        query=query_text,
    )
    has_more = len(attachments) > limit
    page = attachments[:limit]
    return {
        "items": [
            await _attachment_payload(attachment)
            for attachment in page
        ],
        "next_before_id": int(page[-1].id) if has_more and page else None,
    }


async def get_library_attachment(
    db: AsyncSession,
    *,
    user_id: int | str,
    attachment_id: str,
) -> dict[str, Any]:
    """读取当前用户的一个正式附件。"""
    attachment = await _require_attachment(
        AttachmentRepository(db),
        user_id,
        attachment_id,
    )
    return await _attachment_payload(attachment)


async def rename_library_attachment(
    db: AsyncSession,
    *,
    user_id: int | str,
    attachment_id: str,
    file_name: str,
) -> dict[str, Any]:
    """修改附件展示文件名，但不移动 MinIO 对象。"""
    normalized_name = file_name.strip()
    if not normalized_name:
        raise ValueError("附件文件名不能为空")
    if len(normalized_name) > 255:
        raise ValueError("附件文件名不能超过 255 个字符")
    if "/" in normalized_name or chr(92) in normalized_name:
        raise ValueError("附件文件名不能包含路径")

    repository = AttachmentRepository(db)
    attachment = await _require_attachment(
        repository,
        user_id,
        attachment_id,
    )
    if _suffix(normalized_name) != _suffix(str(attachment.attachment_name)):
        raise ValueError("附件改名不能修改文件后缀")

    attachment = await repository.update_attachment_name(
        attachment,
        attachment_name=normalized_name,
    )
    return await _attachment_payload(attachment)


async def delete_library_attachment(
    db: AsyncSession,
    *,
    user_id: int | str,
    attachment_id: str,
) -> None:
    """软删除当前用户的正式附件。"""
    repository = AttachmentRepository(db)
    attachment = await _require_attachment(
        repository,
        user_id,
        attachment_id,
    )
    await repository.soft_delete_attachment(attachment)


async def _require_attachment(
    repository: AttachmentRepository,
    user_id: int | str,
    attachment_id: str,
) -> Attachment:
    try:
        parsed_file_id = UUID(attachment_id)
    except (TypeError, ValueError) as exc:
        raise LookupError("附件不存在或已删除") from exc
    if parsed_file_id.version != 4:
        raise LookupError("附件不存在或已删除")

    attachment = await repository.get_library_attachment_by_file_id_for_user(
        file_id=str(parsed_file_id),
        user_id=user_id,
    )
    if attachment is None:
        raise LookupError("附件不存在或已删除")
    return attachment


async def _attachment_payload(
    attachment: Attachment,
) -> dict[str, Any]:
    access_url = await get_storage().create_file_access_url(
        ATTACHMENT_BUCKET_NAME,
        str(attachment.original_object_name),
    )
    content_type = str(attachment.attachment_type)
    if content_type.startswith("image/"):
        category = "image"
    elif content_type.startswith(("application/", "text/")):
        category = "document"
    else:
        category = "other"

    return {
        "id": str(attachment.file_id),
        "file_name": str(attachment.attachment_name),
        "suffix": _suffix(str(attachment.attachment_name)),
        "content_type": content_type,
        "file_size": int(attachment.attachment_size),
        "category": category,
        "status": str(attachment.status),
        "parse_error": (
            str(attachment.error_message)
            if attachment.error_message is not None
            else None
        ),
        "access_url": access_url,
        "created_at": attachment.created_at,
        "updated_at": attachment.updated_at,
    }


def _suffix(file_name: str) -> str:
    """返回规范化的小写文件后缀。"""
    return Path(file_name).suffix.lower()
