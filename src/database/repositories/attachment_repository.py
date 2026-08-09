from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Attachment


class AttachmentRepository:
    """读写用户拥有的附件资源。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_attachment(
        self,
        *,
        file_id: str,
        user_id: int | str,
        file_name: str,
        content_type: str,
        file_size: int,
        object_name: str,
    ) -> Attachment:
        """创建已上传成功的用户附件。"""
        attachment = Attachment(
            file_id=file_id,
            user_id=int(user_id),
            file_name=file_name,
            content_type=content_type,
            file_size=file_size,
            object_name=object_name,
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
        )
        if before_id is not None:
            statement = statement.where(Attachment.id < before_id)
        if query is not None:
            statement = statement.where(
                Attachment.file_name.ilike(f"%{query}%")
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
            )
        )
        return result.scalar_one_or_none()

    async def list_by_file_ids_for_user(
        self,
        *,
        file_ids: Sequence[str],
        user_id: int | str,
    ) -> list[Attachment]:
        """批量读取当前用户未删除的附件。"""
        if not file_ids:
            return []

        result = await self.session.execute(
            select(Attachment)
            .where(
                Attachment.file_id.in_(file_ids),
                Attachment.user_id == int(user_id),
                Attachment.deleted_at.is_(None),
            )
            .with_for_update()
        )
        return list(result.scalars().all())

    async def update_file_name(
        self,
        attachment: Attachment,
        *,
        file_name: str,
    ) -> Attachment:
        """修改附件展示文件名。"""
        attachment.file_name = file_name
        attachment.updated_at = datetime.now(UTC)
        await self.session.flush()
        return attachment

    async def update_object_name(
        self,
        attachment: Attachment,
        *,
        object_name: str,
    ) -> None:
        """记录附件当前所在的 MinIO 对象名。"""
        attachment.object_name = object_name
        attachment.updated_at = datetime.now(UTC)
        await self.session.flush()

    async def soft_delete_attachment(self, attachment: Attachment) -> None:
        """软删除正式附件。"""
        deleted_at = datetime.now(UTC)
        attachment.deleted_at = deleted_at
        attachment.updated_at = deleted_at
        await self.session.flush()
