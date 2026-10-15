"""Agent 详情配置查询。"""

from sqlalchemy.ext.asyncio import AsyncSession

from server.entities.agent import AgentContextResponse
from src.agents.base_context import BaseContext
from src.database.repositories import AgentRepository


async def get_agent_context(db: AsyncSession, agent_id: str) -> AgentContextResponse | None:
    """用数据库配置覆盖 BaseContext 默认值，返回详情所需的配置字段。"""
    stored = await AgentRepository(db).get_agent_config(agent_id)
    if stored is None:
        return None
    defaults = BaseContext()
    values = {
        key: stored.get(key, getattr(defaults, key))
        for key in AgentContextResponse.model_fields
    }
    if values["skill_root"] is not None:
        values["skill_root"] = str(values["skill_root"])
    return AgentContextResponse(**values)
