from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.agent_library import AgentLibrary
from src.database.models import Agent


class AgentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_by_slug(self, slug: str) -> Agent | None:
        result = await self.session.execute(select(Agent).where(Agent.slug == slug))
        return result.scalar_one_or_none()

    async def ensure_agent(
        self,
        *,
        definition: AgentLibrary,
        role: str = "orchestrator",
        internal_only: bool = False,
    ) -> None:
        """按预设补齐缺失的 Agent，已有 slug 的记录保持原样。"""
        values = {
            "backend_id": definition.backend_id,
            "name": definition.name,
            "description": definition.description,
            "agent_config": definition.context,
            "role": role,
            "is_subagent": role == "subagent",
            "internal_only": internal_only,
        }
        statement = insert(Agent).values(slug=definition.slug, enabled=True, **values)
        statement = statement.on_conflict_do_nothing(index_elements=[Agent.slug])
        await self.session.execute(statement)

    async def list_agents(self, *, role: str, internal_only: bool) -> list[Agent]:
        result = await self.session.execute(
            select(Agent)
            .where(
                Agent.enabled.is_(True),
                Agent.role == role,
                Agent.internal_only.is_(internal_only),
            )
            .order_by(Agent.slug)
        )
        return list(result.scalars().all())

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
            # FIXEME: Resume Run 继续执行原顶层 orchestrator checkpoint。
            "resume": "orchestrator",
            "subagent": "subagent",
        }.get(run_type)
        if expected_role is None:
            return None
        if not agent.enabled or agent.role != expected_role:
            return None
        return agent
