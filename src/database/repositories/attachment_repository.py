from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Attachment

LIBRARY_ATTACHMENT_STATUSES = frozenset(
    {"uploaded", "parsing", "parsed", "failed"}
)


class AttachmentRepository:
    """读写用户拥有的附件资源。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_pending_attachment(
        self,
        *,
        file_id: str,
        user_id: int | str,
        attachment_name: str,
        attachment_type: str,
        attachment_size: int,
        original_object_name: str,
    ) -> Attachment:
        """创建尚未被消息正式使用的上传附件。"""
        attachment = Attachment(
            file_id=file_id,
            user_id=int(user_id),
            status="pending",
            attachment_name=attachment_name,
            attachment_type=attachment_type,
            attachment_size=attachment_size,
            original_object_name=original_object_name,
        )
        self.session.add(attachment)
        await self.session.flush()
        return attachment

    async def list_library_attachments_for_user(
        self,
        *,
        user_id: int | str,
        limit: int,
        before_id: int | None = None,
        query: str | None = None,
    ) -> list[Attachment]:
        """按 ID 倒序读取用户正式附件。"""
        statement = select(Attachment).where(
            Attachment.user_id == int(user_id),
            Attachment.deleted_at.is_(None),
            Attachment.status.in_(LIBRARY_ATTACHMENT_STATUSES),
        )
        if before_id is not None:
            statement = statement.where(Attachment.id < before_id)
        if query is not None:
            statement = statement.where(
                Attachment.attachment_name.ilike(f"%{query}%")
            )

        result = await self.session.execute(
            statement.order_by(Attachment.id.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_library_attachment_by_file_id_for_user(
        self,
        *,
        file_id: str,
        user_id: int | str,
    ) -> Attachment | None:
        """读取当前用户的一个正式附件。"""
        result = await self.session.execute(
            select(Attachment).where(
                Attachment.file_id == file_id,
                Attachment.user_id == int(user_id),
                Attachment.deleted_at.is_(None),
                Attachment.status.in_(LIBRARY_ATTACHMENT_STATUSES),
            )
        )
        return result.scalar_one_or_none()

    async def update_attachment_name(
        self,
        attachment: Attachment,
        *,
        attachment_name: str,
    ) -> Attachment:
        """修改附件展示文件名。"""
        attachment.attachment_name = attachment_name
        attachment.updated_at = datetime.now(UTC)
        await self.session.flush()
        return attachment

    async def soft_delete_attachment(self, attachment: Attachment) -> None:
        """软删除正式附件。"""
        deleted_at = datetime.now(UTC)
        attachment.deleted_at = deleted_at
        attachment.updated_at = deleted_at
        await self.session.flush()
