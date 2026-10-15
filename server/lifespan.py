from contextlib import asynccontextmanager

from fastapi import FastAPI

from server.service.model_service import (
    ensure_builtin_model_providers,
    refresh_model_list_cache,
)
from server.utils.auth import verify_required_auth_settings
from src.agents.backends.sandbox import (
    init_sandbox_provider,
    shutdown_sandbox_provider,
)
from src.database import postgres_manager
from src.storage import close_async_redis_client
from src.utils import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    verify_required_auth_settings()

    # 业务表、LangGraph 迁移和固定 Agent 注册由 ARQ worker startup 单点确保。
    await postgres_manager.initialize()
    try:
        async with postgres_manager.get_async_session_context() as db:
            await ensure_builtin_model_providers(db)
            if not await refresh_model_list_cache(
                db,
                raise_on_database_error=True,
            ):
                logger.warning("Provider 已补齐，但启动时模型列表缓存预热失败。")
        init_sandbox_provider()
        logger.info("FastAPI 服务已启动。")
        yield
    finally:
        await shutdown_sandbox_provider()
        await close_async_redis_client()
        await postgres_manager.dispose()
        logger.info("FastAPI 服务已关闭。")
