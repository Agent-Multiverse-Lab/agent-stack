"""模型供应商持久化与模型引用校验；事务提交由调用方或服务层负责。"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import session_context
from src.database.models import ModelProvider

from .utils import ModelCategory, parse_model_ref


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

    async def require_model(
        self,
        model_ref: str,
        *,
        category: ModelCategory | None = None,
        require_enabled: bool = True,
    ) -> tuple[ModelProvider, dict[str, Any]]:
        """按 provider_id:model_id 查库校验存在性、启用状态与分类。"""
        provider_id, model_id = parse_model_ref(model_ref)

        provider = await self.get_model_provider_by_id(provider_id)
        if provider is None:
            raise LookupError("模型供应商不存在")
        if require_enabled and not provider.is_enabled:
            raise ValueError("模型供应商已停用")

        model = next(
            (
                item
                for item in (provider.enabled_models or [])
                if isinstance(item, dict) and item.get("model_id") == model_id
            ),
            None,
        )
        if model is None:
            raise LookupError("模型未配置")

        actual_category = model.get("category", "chat")
        if category is not None and actual_category != category:
            raise ValueError(
                f"模型类型不匹配：期望 {category}，实际 {actual_category}"
            )
        return provider, model

    async def create_model_provider(
        self, *, provider_id: str, **values: Any
    ) -> ModelProvider:
        provider = ModelProvider(provider_id=provider_id, **values)
        self.session.add(provider)
        await self.session.flush()
        return provider

    async def update_model_provider(
        self, provider_id: str, /, **values: Any
    ) -> ModelProvider | None:
        if "provider_id" in values:
            raise ValueError("不可修改供应商标识")
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


async def fetch_model_config(
    model_ref: str,
    *,
    category: ModelCategory | None = None,
    db: AsyncSession | None = None,
) -> tuple[ModelProvider, dict[str, Any]]:
    """复用已有会话或创建只读会话查询已启用模型配置。"""
    if db is not None:
        return await ModelProviderRepository(db).require_model(model_ref, category=category)
    async with session_context() as session:
        return await ModelProviderRepository(session).require_model(model_ref, category=category)


__all__ = [
    "ModelProviderRepository",
    "fetch_model_config",
]
