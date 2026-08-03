from __future__ import annotations

import inspect
import unittest
from contextlib import asynccontextmanager
from unittest import mock

import src.database.manger as manager_module
from src.agents.leaderagent.agent import LeaderAgent
from src.agents.subagents.citationagent.agent import CitationAgent
from src.agents.subagents.outlineagent.agent import OutlineAgent
from src.agents.subagents.searchagent.agent import SearchAgent
from src.configs.config import Config
from src.database.manger import PostgreManger

_DATABASE_URL = 'postgresql+asyncpg://user:p%40ss@db:5432/app'
_LANGGRAPH_DATABASE_URL = 'postgresql://user:p%40ss@db:5432/app'


class _FakeEngine:
    '''记录数据库引擎释放行为。'''

    def __init__(self, events: list[str]) -> None:
        self.dispose = mock.AsyncMock(
            side_effect=lambda: events.append('dispose:engine')
        )


class _FakePersistence:
    '''提供可断言的 LangGraph setup 方法。'''

    def __init__(self) -> None:
        self.setup = mock.AsyncMock()


def _resource_context(
    resource: object,
    events: list[str],
    name: str,
    *,
    fail: bool = False,
):
    '''构造记录进入和退出顺序的异步资源上下文。'''

    @asynccontextmanager
    async def context():
        events.append(f'enter:{name}')
        if fail:
            raise RuntimeError(f'{name} failed')
        try:
            yield resource
        finally:
            events.append(f'exit:{name}')

    return context()


class LangGraphPostgresPersistenceTest(unittest.IsolatedAsyncioTestCase):
    '''验证 LangGraph PostgreSQL 显式配置、生命周期和接线。'''

    @staticmethod
    def _create_manager(events: list[str]) -> tuple[PostgreManger, _FakeEngine]:
        '''创建不连接真实数据库的 manager。'''

        manager = PostgreManger()
        engine = _FakeEngine(events)
        manager.engine = engine  # type: ignore[assignment]
        manager.session_maker = mock.sentinel.session_maker
        return manager, engine

    def test_langgraph_database_url_is_explicit(self) -> None:
        '''SQLAlchemy 与 LangGraph 分别读取显式配置的连接串。'''

        settings = Config(
            _env_file=None,
            database_url=_DATABASE_URL,
            langgraph_database_url=_LANGGRAPH_DATABASE_URL,
        )

        self.assertEqual(settings.database_url, _DATABASE_URL)
        self.assertEqual(
            settings.langgraph_database_url,
            _LANGGRAPH_DATABASE_URL,
        )

    async def test_process_resources_are_reused_and_closed_in_reverse_order(
        self,
    ) -> None:
        '''单进程复用一对资源，并按 Checkpointer、Store、engine 关闭。'''

        events: list[str] = []
        manager, engine = self._create_manager(events)
        store = _FakePersistence()
        checkpointer = _FakePersistence()

        with self.assertRaisesRegex(RuntimeError, 'is not initialized'):
            manager.get_langgraph_store()
        with self.assertRaisesRegex(RuntimeError, 'is not initialized'):
            manager.get_langgraph_checkpointer()

        with (
            mock.patch.object(
                manager_module.config,
                'langgraph_database_url',
                _LANGGRAPH_DATABASE_URL,
            ),
            mock.patch.object(
                manager_module.AsyncPostgresStore,
                'from_conn_string',
                return_value=_resource_context(store, events, 'store'),
            ) as store_factory,
            mock.patch.object(
                manager_module.AsyncPostgresSaver,
                'from_conn_string',
                return_value=_resource_context(
                    checkpointer,
                    events,
                    'checkpointer',
                ),
            ) as checkpointer_factory,
        ):
            await manager.initialize()
            await manager.initialize()
            await manager.setup_langgraph_persistence()

        store_factory.assert_called_once_with(
            _LANGGRAPH_DATABASE_URL,
            pool_config={'min_size': 1, 'max_size': 10},
        )
        checkpointer_factory.assert_called_once_with(_LANGGRAPH_DATABASE_URL)
        store.setup.assert_awaited_once_with()
        checkpointer.setup.assert_awaited_once_with()

        await manager.dispose()

        self.assertEqual(
            events,
            [
                'enter:store',
                'enter:checkpointer',
                'exit:checkpointer',
                'exit:store',
                'dispose:engine',
            ],
        )
        engine.dispose.assert_awaited_once_with()
        self.assertFalse(manager.initialized)

    async def test_failed_checkpointer_creation_releases_open_resources(
        self,
    ) -> None:
        '''Checkpointer 创建失败时释放 Store 和 engine。'''

        events: list[str] = []
        manager, engine = self._create_manager(events)
        with (
            mock.patch.object(
                manager_module.config,
                'langgraph_database_url',
                _LANGGRAPH_DATABASE_URL,
            ),
            mock.patch.object(
                manager_module.AsyncPostgresStore,
                'from_conn_string',
                return_value=_resource_context(object(), events, 'store'),
            ),
            mock.patch.object(
                manager_module.AsyncPostgresSaver,
                'from_conn_string',
                return_value=_resource_context(
                    object(),
                    events,
                    'checkpointer',
                    fail=True,
                ),
            ),
            mock.patch.object(manager_module.logger, 'exception'),
        ):
            with self.assertRaisesRegex(RuntimeError, 'checkpointer failed'):
                await manager.initialize()

        self.assertEqual(
            events,
            [
                'enter:store',
                'enter:checkpointer',
                'exit:store',
                'dispose:engine',
            ],
        )
        engine.dispose.assert_awaited_once_with()
        self.assertFalse(manager.initialized)

    def test_all_concrete_agents_bind_store_and_checkpointer(self) -> None:
        '''四个真实 create_agent 调用点同时注入两个组件。'''

        methods = (
            LeaderAgent._build_agent,
            CitationAgent.get_agent,
            SearchAgent.get_agent,
            OutlineAgent.get_agent,
        )
        for method in methods:
            with self.subTest(method=method.__qualname__):
                source = inspect.getsource(method)
                self.assertIn('store=self.get_store()', source)
                self.assertIn(
                    'checkpointer=self.get_checkpointer()',
                    source,
                )


if __name__ == '__main__':
    unittest.main()
