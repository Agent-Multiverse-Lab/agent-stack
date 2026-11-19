from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import AgentRun, AgentRunRequest


class AgentRunRequestRepository:
    """输入关联与等待队列；由 Service 持有 Conversation 行锁后调用，不提交事务。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_request_id(self, request_id: str) -> AgentRunRequest | None:
        result = await self.session.execute(
            select(AgentRunRequest).where(AgentRunRequest.request_id == request_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def create_request(
        self, *, request_id: str, uid: str, thread_id: str, agent_id: str,
        trigger_message_id: int, dispatch_policy: str, status: str,
        queue_seq: int | None = None,
    ) -> AgentRunRequest:
        request = AgentRunRequest(
            request_id=request_id, uid=uid, thread_id=thread_id, agent_id=agent_id,
            trigger_message_id=trigger_message_id, dispatch_policy=dispatch_policy,
            status=status, queue_seq=queue_seq,
        )
        self.session.add(request)
        await self.session.flush()
        return request

    async def get_next_queue_seq(self, thread_id: str) -> int:
        result = await self.session.execute(select(func.max(AgentRunRequest.queue_seq)).where(
            AgentRunRequest.thread_id == thread_id,
        ))
        return int(result.scalar() or 0) + 1

    async def has_queued_steer_for_thread(self, thread_id: str) -> bool:
        result = await self.session.execute(select(AgentRunRequest.request_id).where(
            AgentRunRequest.thread_id == thread_id, AgentRunRequest.status == "queued",
            AgentRunRequest.dispatch_policy == "steer",
        ).limit(1))
        return result.scalar_one_or_none() is not None

    async def has_expired_steer_for_run(self, run_id: str, *, grace_seconds: float) -> bool:
        result = await self.session.execute(select(AgentRunRequest.request_id).join(
            AgentRun, AgentRun.thread_id == AgentRunRequest.thread_id,
        ).where(
            AgentRun.id == run_id, AgentRunRequest.status == "queued",
            AgentRunRequest.dispatch_policy == "steer",
            AgentRunRequest.created_at <= datetime.now(UTC) - timedelta(seconds=grace_seconds),
        ).limit(1))
        return result.scalar_one_or_none() is not None

    async def pop_next_queued_for_thread(self, thread_id: str) -> AgentRunRequest | None:
        result = await self.session.execute(select(AgentRunRequest).where(
            AgentRunRequest.thread_id == thread_id, AgentRunRequest.status == "queued",
        ).order_by(AgentRunRequest.queue_seq).limit(1).with_for_update())
        return result.scalar_one_or_none()

    async def mark_dispatched(self, request_id: str) -> None:
        await self.session.execute(update(AgentRunRequest).where(
            AgentRunRequest.request_id == request_id, AgentRunRequest.status == "queued",
        ).values(status="dispatched"))
