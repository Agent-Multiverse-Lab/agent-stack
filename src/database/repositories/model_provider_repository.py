"""模型供应商持久化；仅处理 ModelProvider ORM，事务提交由 Service 负责。"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import ModelProvider


class ModelProviderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_model_providers(
        self, *, enabled_only: bool = False
    ) -> list[ModelProvider]:
        query = select(ModelProvider).order_by(ModelProvider.provider_id)
        if enabled_only:
            query = query.where(ModelProvider.is_enabled.is_(True))
        result = await self.session.execute(query.execution_options(populate_existing=True))
        return list(result.scalars().all())

    async def get_model_provider_by_id(self, provider_id: str) -> ModelProvider | None:
        result = await self.session.execute(
            select(ModelProvider)
            .where(ModelProvider.provider_id == provider_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def create_model_provider(
        self, *, provider_id: str, **values: Any
    ) -> ModelProvider:
        if "user_id" in values:
            raise ValueError("不可设置用户归属")
        provider = ModelProvider(provider_id=provider_id, **values)
        self.session.add(provider)
        await self.session.flush()
        return provider

    async def update_model_provider(
        self, provider_id: str, /, **values: Any
    ) -> ModelProvider | None:
        if {"user_id", "provider_id"} & values.keys():
            raise ValueError("不可修改供应商标识或设置用户归属")
        provider = await self.get_model_provider_by_id(provider_id)
        if provider is None:
            return None
        for field, value in values.items():
            setattr(provider, field, value)
        await self.session.flush()
        return provider

    async def delete_model_provider(self, provider_id: str) -> bool:
        provider = await self.get_model_provider_by_id(provider_id)
        if provider is None:
            return False
        await self.session.delete(provider)
        await self.session.flush()
        return True
