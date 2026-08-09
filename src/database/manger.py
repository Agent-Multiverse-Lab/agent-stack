import asyncio
import json
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import AsyncPostgresStore, PoolConfig
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.sql import text

from src.configs.config import config
from src.utils.logger import logger

from .base import Base

_NOT_INITIALIZED_MSG = "PostgreManger is not initialized."


class PostgreManger:
    """PostgreSQL 运行时资源的唯一管理者。
    """

    def __init__(self) -> None:
        # engine 与 session_maker 通过 get_engine() / get_session_maker() 懒加载，不外部注入。
        self.engine: AsyncEngine | None = None
        self.session_maker: async_sessionmaker[AsyncSession] | None = None
        self.langgraph_store: AsyncPostgresStore | None = None
        self.langgraph_checkpointer: AsyncPostgresSaver | None = None
        self._langgraph_resource_stack: AsyncExitStack | None = None
        # 初始化标记，防止重复初始化，并作为依赖方法的显式前置条件。
        self.initialized: bool = False

    def get_engine(self) -> AsyncEngine:
        """复用或创建 SQLAlchemy async engine。"""
        if self.engine is not None:
            return self.engine
        if not config.database_url:
            raise RuntimeError("Missing DATABASE_URL")
        self.engine = create_async_engine(
            config.database_url,
            echo=False,
            json_serializer=lambda obj: json.dumps(obj, ensure_ascii=False),
            json_deserializer=json.loads,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=10,
            max_overflow=20,
        )
        return self.engine

    def get_session_maker(self) -> async_sessionmaker[AsyncSession]:
        """复用或创建 async session factory。"""
        if self.session_maker is None:
            self.session_maker = async_sessionmaker(
                self.get_engine(),
                expire_on_commit=False,
                class_=AsyncSession,
            )
        return self.session_maker

    async def initialize(self) -> None:
        """统一启动入口，只做资源准备，不做破坏性操作。"""
        if self.initialized:
            return

        resource_stack = AsyncExitStack()
        await resource_stack.__aenter__()
        try:
            langgraph_database_url = config.langgraph_database_url
            if not langgraph_database_url:
                raise RuntimeError("Missing LANGGRAPH_DATABASE_URL")
                

            engine = self.get_engine()
            resource_stack.push_async_callback(engine.dispose)
            self.get_session_maker()

            store_pool_config = PoolConfig(min_size=1, max_size=10)
            langgraph_store = await resource_stack.enter_async_context(
                AsyncPostgresStore.from_conn_string(
                    langgraph_database_url,
                    pool_config=store_pool_config,
                )
            )
            langgraph_checkpointer = await resource_stack.enter_async_context(
                AsyncPostgresSaver.from_conn_string(langgraph_database_url)
            )
        except asyncio.CancelledError:
            await resource_stack.aclose()
            self._reset_resource_references()
            raise
        except Exception:
            logger.exception('PostgreSQL 运行时资源初始化失败')
            try:
                await resource_stack.aclose()
            except Exception:
                logger.exception('PostgreSQL 初始化失败后的资源清理失败')
            self._reset_resource_references()
            raise

        self.langgraph_store = langgraph_store
        self.langgraph_checkpointer = langgraph_checkpointer
        self._langgraph_resource_stack = resource_stack
        self.initialized = True

    def get_langgraph_store(self) -> AsyncPostgresStore:
        '''获取当前进程已初始化的 LangGraph Store。'''

        if not self.initialized or self.langgraph_store is None:
            raise RuntimeError(_NOT_INITIALIZED_MSG)
        return self.langgraph_store

    def get_langgraph_checkpointer(self) -> AsyncPostgresSaver:
        '''获取当前进程已初始化的 LangGraph Checkpointer。'''

        if not self.initialized or self.langgraph_checkpointer is None:
            raise RuntimeError(_NOT_INITIALIZED_MSG)
        return self.langgraph_checkpointer

    async def setup_langgraph_persistence(self) -> None:
        '''创建或迁移 LangGraph Store 与 Checkpointer 表。'''

        await self.get_langgraph_store().setup()
        await self.get_langgraph_checkpointer().setup()

    async def ensure_tables_exist(self) -> None:
        """创建缺失表，并补充 Agent Run 的非破坏性类型字段。"""
        if not self.initialized:
            raise RuntimeError(_NOT_INITIALIZED_MSG)
        async with self.get_engine().begin() as connection:
            await connection.run_sync(
                lambda sync_connection: Base.metadata.create_all(
                    bind=sync_connection,
                    checkfirst=True,
                )
            )
            await connection.execute(
                text(
                    "ALTER TABLE agent_run "
                    "ADD COLUMN IF NOT EXISTS run_type VARCHAR(32) "
                    "NOT NULL DEFAULT 'chat'"
                )
            )
            await connection.execute(
                text(
                    "UPDATE agent_run AS ar "
                    "SET run_type = CASE "
                    "WHEN a.role = 'subagent' THEN 'subagent' ELSE 'chat' END "
                    "FROM agent AS a "
                    "WHERE a.slug = ar.agent_id "
                    "AND ar.run_type IS DISTINCT FROM CASE "
                    "WHEN a.role = 'subagent' THEN 'subagent' ELSE 'chat' END"
                )
            )
            await connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_agent_run_run_type "
                    "ON agent_run (run_type)"
                )
            )

    async def create_tables(self) -> None:
        """兼容旧调用；实际执行非破坏性的表存在性检查。"""
        await self.ensure_tables_exist()

    @asynccontextmanager
    async def get_async_session_context(self) -> AsyncGenerator[AsyncSession]:
        """提供 async session 上下文，退出时自动提交。"""
        if not self.initialized:
            raise RuntimeError(_NOT_INITIALIZED_MSG)
        async with self.get_session_maker()() as session:
            yield session
            await session.commit()

    async def dispose(self) -> None:
        """释放所有持有的资源，并重置到未初始化状态。"""
        resource_stack = self._langgraph_resource_stack
        engine = self.engine
        try:
            if resource_stack is not None:
                await resource_stack.aclose()
            elif engine is not None:
                await engine.dispose()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('PostgreSQL 运行时资源释放失败')
            raise
        finally:
            self._reset_resource_references()

    def _reset_resource_references(self) -> None:
        '''清空当前进程持有的 PostgreSQL 资源引用。'''

        self.langgraph_store = None
        self.langgraph_checkpointer = None
        self._langgraph_resource_stack = None
        self.engine = None
        self.session_maker = None
        self.initialized = False


postgres_manager = PostgreManger()
