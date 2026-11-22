from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import AgentRunRequest


class AgentRunRequestRepository:
    """AgentRunRequest 基础持久化与查询；由 Service 在事务内调用，不提交事务。"""

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
