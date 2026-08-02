from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Agent


class AgentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_by_slug(self, slug: str) -> Agent | None:
        result = await self.session.execute(
            select(Agent).where(Agent.slug == slug)
        )
        return result.scalar_one_or_none()

    async def ensure_agent_registered(
        self,
        *,
        slug: str,
        backend_id: str,
        name: str,
        description: str,
        role: str = "orchestrator",
        internal_only: bool = False,
    ) -> Agent:
        """补充缺失的固定 Agent 注册，不覆盖数据库中的已有记录。"""

        agent = await self._get_by_slug(slug)
        if agent is not None:
            return agent

        agent = Agent(
            slug=slug,
            backend_id=backend_id,
            name=name,
            role=role,
            description=description,
            agent_config={},
            internal_only=internal_only,
            enabled=True,
        )
        self.session.add(agent)
        await self.session.flush()
        return agent

    async def get_by_slug_for_run_type(
        self,
        slug: str,
        run_type: str = "chat",
    ) -> Agent | None:
        """按 slug 查询已启用且角色匹配 Run 类型的 Agent。"""

        agent = await self._get_by_slug(slug)
        if not agent:
            return None

        expected_role = {
            "chat": "orchestrator",
            "subagent": "subagent",
        }.get(run_type)
        if expected_role is None:
            return None
        if not agent.enabled or agent.role != expected_role:
            return None
        return agent
