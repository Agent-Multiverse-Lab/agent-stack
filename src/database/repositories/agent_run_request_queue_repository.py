from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import AgentRun, AgentRunRequest, Conversation
from src.database.repositories.agent_run_repository import AgentRunRepository
from src.database.repositories.conversation_repository import ConversationRepository

_QUEUE_ORDER = (
    case((AgentRunRequest.dispatch_policy == "steer", 0), else_=1),
    AgentRunRequest.queue_seq.asc(),
)


class AgentRunRequestQueueRepository:
    """请求等待队列及 AgentRunRequest 向 AgentRun 转换持久化；由持会话锁的 Service 调用。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_next_queue_seq(self, thread_id: str) -> int:
        result = await self.session.execute(
            select(func.max(AgentRunRequest.queue_seq)).where(
                AgentRunRequest.thread_id == thread_id,
            )
        )
        return int(result.scalar() or 0) + 1

    async def list_queued_for_thread(
        self, thread_id: str, *, uid: str
    ) -> list[AgentRunRequest]:
        result = await self.session.execute(
            select(AgentRunRequest)
            .where(
                AgentRunRequest.thread_id == thread_id,
                AgentRunRequest.uid == uid,
                AgentRunRequest.status == "queued",
            )
            .options(selectinload(AgentRunRequest.trigger_message))
            .order_by(*_QUEUE_ORDER)
            .execution_options(populate_existing=True)
        )
        return list(result.scalars().all())

    async def get_queue_position(
        self, thread_id: str, request_id: str, *, uid: str
    ) -> int:
        queued = await self.list_queued_for_thread(thread_id, uid=uid)
        for index, item in enumerate(queued, start=1):
            if str(item.request_id) == request_id:
                return index
        return len(queued) or 1

    async def has_queued_steer_for_thread(self, thread_id: str) -> bool:
        result = await self.session.execute(
            select(AgentRunRequest.request_id)
            .where(
                AgentRunRequest.thread_id == thread_id,
                AgentRunRequest.status == "queued",
                AgentRunRequest.dispatch_policy == "steer",
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def has_expired_steer_for_run(
        self, run_id: str, *, grace_seconds: float
    ) -> bool:
        result = await self.session.execute(
            select(AgentRunRequest.request_id)
            .join(AgentRun, AgentRun.thread_id == AgentRunRequest.thread_id)
            .where(
                AgentRun.id == run_id,
                AgentRunRequest.status == "queued",
                AgentRunRequest.dispatch_policy == "steer",
                AgentRunRequest.created_at
                <= datetime.now(UTC) - timedelta(seconds=grace_seconds),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def pop_next_queued_for_thread(
        self, thread_id: str
    ) -> AgentRunRequest | None:
        result = await self.session.execute(
            select(AgentRunRequest)
            .where(
                AgentRunRequest.thread_id == thread_id,
                AgentRunRequest.status == "queued",
            )
            .order_by(*_QUEUE_ORDER)
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def _lock_queued_request(
        self, request_id: str, *, uid: str
    ) -> AgentRunRequest | None:
        result = await self.session.execute(
            select(AgentRunRequest)
            .where(
                AgentRunRequest.request_id == request_id,
                AgentRunRequest.uid == uid,
                AgentRunRequest.status == "queued",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def upgrade_queued_to_steer(
        self, request_id: str, *, uid: str
    ) -> AgentRunRequest | None:
        request = await self._lock_queued_request(request_id, uid=uid)
        if request is None:
            return None
        request.dispatch_policy = "steer"
        await self.session.flush()
        return request

    async def mark_dispatched(self, request_id: str) -> None:
        await self.session.execute(
            update(AgentRunRequest)
            .where(
                AgentRunRequest.request_id == request_id,
                AgentRunRequest.status == "queued",
            )
            .values(status="dispatched")
        )
        await self.session.flush()

    async def cancel_queued_request(
        self, request_id: str, *, uid: str
    ) -> AgentRunRequest | None:
        request = await self._lock_queued_request(request_id, uid=uid)
        if request is None:
            return None
        request.status = "cancelled"
        await self.session.flush()
        await ConversationRepository(self.session).cancel_queued_input_message(
            int(request.trigger_message_id)
        )
        return request

    async def dispatch_request_to_run(
        self,
        *,
        request: AgentRunRequest,
        conversation: Conversation,
        run_metadata: dict[str, Any],
        run_id: str | None = None,
    ) -> AgentRun:
        """在当前事务内将 AgentRunRequest 落库转换为 AgentRun，并晋升或绑定输入消息。"""
        was_queued = request.status == "queued"
        run = await AgentRunRepository(self.session).create_run(
            run_id=run_id or str(uuid.uuid4()),
            thread_id=str(request.thread_id),
            conversation_id=int(conversation.id),
            uid=str(request.uid),
            agent_slug=str(request.agent_id),
            request_id=str(request.request_id),
            trigger_message_id=int(request.trigger_message_id),
            run_type="chat",
            run_metadata=run_metadata,
        )
        conversations = ConversationRepository(self.session)
        if was_queued:
            await conversations.promote_queued_input_message(
                int(request.trigger_message_id), str(run.id)
            )
            await self.mark_dispatched(str(request.request_id))
            request.status = "dispatched"
        else:
            await conversations.bind_input_message_to_run(run)
        return run
