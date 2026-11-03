"""工作区的目录归属、模型绑定和逐文件任务结果。"""

import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from server.entities.knowledge_workspace import KnowledgeBaseUpdate, KnowledgeFileUpdate, KnowledgeFolderCreate
from server.service import knowledge_workspace_service as service
from src.database.models import KnowledgeBase, KnowledgeEmbeddingBinding, KnowledgeFile, KnowledgeFolder, KnowledgeTask, User
from src.database.repositories.knowledge_workspace_repository import KnowledgeWorkspaceRepository


class AsyncSessionAdapter:
    """用真实 SQLite 查询验证服务事务，不连接开发数据库。"""
    def __init__(self, session):
        self.session = session

    async def execute(self, statement): return self.session.execute(statement)
    async def scalars(self, statement): return self.session.scalars(statement)
    async def get(self, model, key): return self.session.get(model, key)
    async def flush(self): self.session.flush()
    async def commit(self): self.session.commit()
    async def rollback(self): self.session.rollback()
    async def delete(self, row): self.session.delete(row)
    def add(self, row): self.session.add(row)


class KnowledgeWorkspaceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        tables = [model.__table__ for model in (User, KnowledgeBase, KnowledgeFolder, KnowledgeFile, KnowledgeEmbeddingBinding, KnowledgeTask)]
        KnowledgeBase.metadata.create_all(self.engine, tables=tables)
        self.session = Session(self.engine, expire_on_commit=False)
        self.db = AsyncSessionAdapter(self.session)
        self.session.add_all([User(uid='u1', email='u1@test', password_hash='x'), User(uid='u2', email='u2@test', password_hash='x')])
        self.session.add_all([KnowledgeBase(kb_id='kb1', uid='u1', name='Docs', description='', settings={}), KnowledgeBase(kb_id='kb2', uid='u2', name='Other', description='', settings={})])
        self.session.add_all([KnowledgeFile(file_id='f1', kb_id='kb1', original_file_name='one.txt', original_object_name='original/one', content_type='text/plain', file_size=1), KnowledgeFile(file_id='f2', kb_id='kb1', original_file_name='two.txt', original_object_name='original/two', content_type='text/plain', file_size=1), KnowledgeFile(file_id='foreign', kb_id='kb2', original_file_name='private.txt', original_object_name='original/private', content_type='text/plain', file_size=1)])
        self.session.commit()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    async def test_owner_and_folder_cycle(self):
        with self.assertRaises(LookupError):
            await service.list_folders(self.db, 'u2', 'kb1')
        root = await service.save_folder(self.db, 'u1', 'kb1', KnowledgeFolderCreate(name='A'))
        child = await service.save_folder(self.db, 'u1', 'kb1', KnowledgeFolderCreate(name='B', parent_id=root['folder_id']))
        with self.assertRaisesRegex(ValueError, '子目录'):
            await service.save_folder(self.db, 'u1', 'kb1', KnowledgeFolderCreate(name='A', parent_id=child['folder_id']), root['folder_id'])

    async def test_move_keeps_object_identity_and_rejects_foreign_folder(self):
        folder = await service.save_folder(self.db, 'u1', 'kb1', KnowledgeFolderCreate(name='Manuals'))
        await service.update_file(self.db, 'u1', 'kb1', 'f1', KnowledgeFileUpdate(name='renamed.txt', folder_id=folder['folder_id']))
        row = self.session.get(KnowledgeFile, 'f1')
        self.assertEqual(row.original_object_name, 'original/one')
        self.assertEqual(row.original_file_name, 'renamed.txt')
        with self.assertRaisesRegex(ValueError, '内容'):
            await service.delete_folder(self.db, 'u1', 'kb1', folder['folder_id'])
        foreign = await service.save_folder(self.db, 'u2', 'kb2', KnowledgeFolderCreate(name='Private'))
        with self.assertRaises(LookupError):
            await service.update_file(self.db, 'u1', 'kb1', 'f1', KnowledgeFileUpdate(name='x', folder_id=foreign['folder_id']))

    async def test_bound_model_cannot_be_replaced(self):
        self.session.add(KnowledgeEmbeddingBinding(uid='u1', kb_id='kb1', collection_name='collection', embedding_model_spec='provider/bound', embedding_dimension=3, embedding_batch_size=1))
        self.session.commit()
        payload = KnowledgeBaseUpdate(name='Docs', settings={'embedding_model_spec': 'provider/other'})
        with self.assertRaisesRegex(ValueError, '不能更换'):
            await service.update_settings(self.db, 'u1', 'kb1', payload)

    async def test_batch_keeps_success_and_failure_and_does_not_repeat(self):
        queue = SimpleNamespace(enqueue_job=AsyncMock(return_value=object()))
        with patch.object(service, 'get_arq_pool', AsyncMock(return_value=queue)):
            task = await service.create_task(self.db, 'u1', 'kb1', 'parse', {'file_ids': ['f1', 'f2']})
        with self.assertRaisesRegex(ValueError, '未完成'):
            await service.create_task(self.db, 'u1', 'kb1', 'parse', {'file_ids': ['f1']})

        @asynccontextmanager
        async def context(): yield self.db

        parse = AsyncMock(side_effect=[ValueError('broken PDF'), object()])
        with patch.object(service, 'session_context', context), patch.object(service.knowledge_service, 'parse_file', parse):
            await service.process_knowledge_task({}, task['task_id'])
            await service.process_knowledge_task({}, task['task_id'])
        row = await KnowledgeWorkspaceRepository(self.db).task(task['task_id'])
        self.assertEqual(row.status, 'failed')
        self.assertEqual([item['success'] for item in row.results], [False, True])
        self.assertEqual(row.results[0]['error'], 'broken PDF')
        self.assertEqual(parse.await_count, 2)

    async def test_batch_rejects_foreign_file(self):
        with self.assertRaises(LookupError):
            await service.create_task(self.db, 'u1', 'kb1', 'parse', {'file_ids': ['foreign']})

    async def test_cancel_pending_task(self):
        queue = SimpleNamespace(enqueue_job=AsyncMock(return_value=object()))
        with patch.object(service, 'get_arq_pool', AsyncMock(return_value=queue)):
            task = await service.create_task(self.db, 'u1', 'kb1', 'parse', {'file_ids': ['f1']})
        cancelled = await service.cancel_task(self.db, 'u1', 'kb1', task['task_id'])
        self.assertEqual(cancelled['status'], 'cancelled')
