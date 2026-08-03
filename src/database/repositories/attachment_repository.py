from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Attachment


class AttachmentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_pending(
        self,
        *,
        user_id: str,
        attachment_name: str,
        attachment_type: str,
        attachment_size: int,
        attachment_path: str,
    ) -> Attachment:
        attachment = Attachment(
            uid=int(user_id),
            conversation_id=None,
            status="pending",
            attachment_name=attachment_name,
            attachment_type=attachment_type,
            attachment_size=attachment_size,
            attachment_path=attachment_path,
        )
        self.session.add(attachment)
        await self.session.flush()
        return attachment

    async def get_by_id_for_user(
        self,
        attachment_id: str,
        user_id: str,
    ) -> Attachment | None:
        try:
            attachment_pk = int(attachment_id)
        except (TypeError, ValueError):
            return None

        result = await self.session.execute(
            select(Attachment).where(
                Attachment.id == attachment_pk,
                Attachment.uid == int(user_id),
            )
        )
        return result.scalar_one_or_none()

    async def mark_attached(
        self,
        attachment: Attachment,
        *,
        conversation_id: str,
        attachment_path: str,
    ) -> Attachment:
        attachment.status = "attached"
        attachment.conversation_id = int(conversation_id)
        attachment.attachment_path = attachment_path
        await self.session.flush()
        return attachment
