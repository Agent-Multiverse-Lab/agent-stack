"""模型供应商持久化；事务提交由 Service 负责。"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import ModelProvider


class ModelRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_provider_by_id(self, provider_id: str) -> ModelProvider | None:
        result = await self.session.execute(
            select(ModelProvider)
            .where(ModelProvider.provider_id == provider_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list_providers(self, *, enabled_only: bool = False) -> list[ModelProvider]:
        query = select(ModelProvider).order_by(ModelProvider.provider_id)
        if enabled_only:
            query = query.where(ModelProvider.is_enabled.is_(True))
        result = await self.session.execute(query.execution_options(populate_existing=True))
        return list(result.scalars().all())

    async def create_provider(self, **values: Any) -> ModelProvider:
        provider = ModelProvider(**values)
        self.session.add(provider)
        await self.session.flush()
        return provider

    async def insert_provider_if_missing(self, **values: Any) -> None:
        await self.session.execute(
            insert(ModelProvider)
            .values(**values)
            .on_conflict_do_nothing(index_elements=[ModelProvider.provider_id])
        )
        await self.session.flush()

    async def update_provider(self, provider: ModelProvider, **values: Any) -> ModelProvider:
        if {"user_id", "provider_id"} & values.keys():
            raise ValueError("不可修改供应商标识或设置用户归属")
        for field, value in values.items():
            setattr(provider, field, value)
        await self.session.flush()
        return provider

    async def delete_provider(self, provider: ModelProvider) -> None:
        await self.session.delete(provider)
        await self.session.flush()
