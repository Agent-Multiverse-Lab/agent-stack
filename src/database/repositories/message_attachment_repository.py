from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Attachment, MessageAttachment


class MessageAttachmentRepository:
    """读写 Message 对 Attachment 的有序引用。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_links(
        self,
        *,
        message_id: int,
        attachments: Sequence[Attachment],
    ) -> None:
        """按输入顺序创建 Message 对 Attachment 的引用。"""
        if not attachments:
            return

        self.session.add_all(
            [
                MessageAttachment(
                    message_id=message_id,
                    attachment_id=int(attachment.id),
                    position=position,
                )
                for position, attachment in enumerate(attachments)
            ]
        )
        await self.session.flush()

    async def list_attachments_by_message_ids(
        self,
        message_ids: Sequence[int],
    ) -> list[tuple[MessageAttachment, Attachment]]:
        """批量读取多条消息的有序附件。"""
        if not message_ids:
            return []

        result = await self.session.execute(
            select(MessageAttachment, Attachment)
            .join(
                Attachment,
                Attachment.id == MessageAttachment.attachment_id,
            )
            .where(MessageAttachment.message_id.in_(message_ids))
            .order_by(
                MessageAttachment.message_id.asc(),
                MessageAttachment.position.asc(),
            )
            .execution_options(populate_existing=True)
        )
        return [(row[0], row[1]) for row in result.all()]
