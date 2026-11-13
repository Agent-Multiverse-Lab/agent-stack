from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import AgentRunRequest


class AgentRunRequestRepository:
    """保存和查询请求关联；事务由 Service 提交。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_request_id(self, request_id: str) -> AgentRunRequest | None:
        """获取当前的req记录"""
        result = await self.session.execute(
            select(AgentRunRequest).where(AgentRunRequest.request_id == request_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def create_request(
        self,
        *,
        request_id: str,
        uid: str,
        conversation_id: int,
        thread_id: str,
        agent_id: str,
        trigger_message_id: int,
    ) -> AgentRunRequest:
        request = AgentRunRequest(
            request_id=request_id,
            uid=uid,
            conversation_id=conversation_id,
            thread_id=thread_id,
            agent_id=agent_id,
            trigger_message_id=trigger_message_id,
        )
        self.session.add(request)
        await self.session.flush()
        return request
