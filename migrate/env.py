from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import src.database.models  # noqa: F401
from src.configs import config as app_config
from src.database.base import Base

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """在不创建数据库连接的情况下生成迁移 SQL。"""

    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """通过异步数据库连接执行迁移。"""

    asyncio.run(_run_async_migrations())


async def _run_async_migrations() -> None:
    """创建 Alembic 专用连接并运行同步迁移上下文。"""

    connectable = create_async_engine(
        _database_url(),
        poolclass=pool.NullPool,
    )
    try:
        async with connectable.connect() as connection:
            await connection.run_sync(_run_migrations)
    finally:
        await connectable.dispose()


def _run_migrations(connection: Connection) -> None:
    """把 Alembic 迁移绑定到当前数据库连接。"""

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def _database_url() -> str:
    """读取当前项目配置中的 PostgreSQL 地址。"""

    if not app_config.database_url:
        raise RuntimeError("缺少 DATABASE_URL")
    return app_config.database_url


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
