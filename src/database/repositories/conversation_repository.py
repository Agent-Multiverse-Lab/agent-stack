from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Conversation, Message


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_conversation_by_id(
        self,
        conversation_id: int | str,
    ) -> Conversation | None:
        result = await self.session.execute(
            select(Conversation)
            .where(Conversation.id == int(conversation_id))
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_conversation_by_thread_id_for_user(
        self,
        thread_id: str,
        user_id: str,
    ) -> Conversation | None:
        result = await self.session.execute(
            select(Conversation).where(
                Conversation.thread_id == thread_id,
                Conversation.uid == str(user_id),
            )
        )
        return result.scalar_one_or_none()

    async def create_conversation(
        self,
        uid: str,
        thread_id: str,
        agent_slug: str,
        parent_conversation_id: int | None = None,
        title: str | None = None,
        summary: str | None = None,
        conversation_metadata: dict | None = None,
    ) -> Conversation:
        conversation = Conversation(
            uid=uid,
            thread_id=thread_id,
            agent_id=agent_slug,
            parent_conversation_id=parent_conversation_id,
            title=title or "",
            summary=summary,
            conversation_metadata=conversation_metadata,
        )
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def create_agent_input_message(
        self,
        *,
        conversation_id: int | str,
        content: str,
        image_content: str | None = None,
        message_type: str = "text",
    ) -> Message:
        return await self._create_message(
            conversation_id=conversation_id,
            role="user",
            content=content,
            image_content=image_content,
            message_type=message_type,
        )

    async def create_agent_output_message(
        self,
        *,
        conversation_id: int | str,
        agent_run_id: str,
        content: str,
    ) -> Message:
        return await self._create_message(
            conversation_id=conversation_id,
            agent_run_id=agent_run_id,
            role="assistant",
            content=content,
        )

    async def _create_message(
        self,
        *,
        conversation_id: int | str,
        role: str,
        content: str,
        agent_run_id: str | None = None,
        request_id: str | None = None,
        image_content: str | None = None,
        message_type: str = "text",
        status: str = "completed",
    ) -> Message:
        message = Message(
            conversation_id=int(conversation_id),
            agent_run_id=agent_run_id,
            role=role,
            content=content,
            image_content=image_content,
            request_id=request_id,
            message_type=message_type,
            status=status,
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def get_run_result_message(
        self,
        run_id: str,
    ) -> Message | None:
        result = await self.session.execute(
            select(Message)
            .where(
                Message.agent_run_id == run_id,
                Message.role == "assistant",
            )
            .order_by(Message.id.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()
