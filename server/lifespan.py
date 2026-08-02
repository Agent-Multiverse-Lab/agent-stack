from contextlib import asynccontextmanager

from fastapi import FastAPI

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

    # 表结构和固定 Agent 注册由 ARQ worker startup 单点确保。
    await postgres_manager.initialize()
    try:
        init_sandbox_provider()
        logger.info("FastAPI 服务已启动。")
        yield
    finally:
        await shutdown_sandbox_provider()
        await close_async_redis_client()
        await postgres_manager.dispose()
        logger.info("FastAPI 服务已关闭。")
