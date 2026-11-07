"""知识库工作区：配置、目录、批任务和检索评估。"""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from server.entities.knowledge_workspace import KnowledgeSettings
from server.service import knowledge_service
from server.service.arq_queue_servcie import get_arq_pool
from src.configs import config
from src.database.models import KnowledgeFolder, KnowledgeTask
from src.database.repositories.knowledge_repository import KnowledgeEmbeddingBindingRepository
from src.database.repositories.knowledge_workspace_repository import KnowledgeWorkspaceRepository
from src.database.session import session_context
from src.knowledge.rag_eval.evaluator import RetrievalEvaluator
from src.knowledge.rag_eval.types import RetrievalDataset


def folder_data(row):
    return {'folder_id': row.folder_id, 'parent_id': row.parent_id, 'name': row.name}


def task_data(row):
    return {
        'task_id': row.task_id, 'kb_id': row.kb_id, 'operation': row.operation,
        'status': row.status, 'total': len(row.payload.get('file_ids', row.payload.get('samples', []))),
        'completed': len(row.results), 'results': row.results, 'report': row.report,
        'error': row.error, 'created_at': row.created_at, 'finished_at': row.finished_at,
    }


async def get_settings(db, uid, kb_id):
    base = await KnowledgeWorkspaceRepository(db).require_base(uid, kb_id)
    binding = await KnowledgeEmbeddingBindingRepository(db).get(uid=uid, kb_id=kb_id)
    return {
        'kb_id': kb_id, 'name': base.name, 'description': base.description, 'status': base.status,
        'settings': KnowledgeSettings.model_validate(base.settings).model_dump(),
        'embedding_model_spec': binding.embedding_model_spec if binding else None,
    }


async def update_settings(db, uid, kb_id, payload):
    base = await KnowledgeWorkspaceRepository(db).require_base(uid, kb_id, lock=True)
    binding = await KnowledgeEmbeddingBindingRepository(db).get(uid=uid, kb_id=kb_id)
    requested = payload.settings.embedding_model_spec
    if binding and requested and requested != binding.embedding_model_spec:
        raise ValueError('已建立索引的知识库不能更换 Embedding 模型')
    if requested:
        knowledge_service.resolve_embedding_model(requested)
    base.name, base.description = payload.name, payload.description.strip()
    base.settings = payload.settings.model_dump()
    await db.commit()
    return await get_settings(db, uid, kb_id)


async def list_folders(db, uid, kb_id):
    repo = KnowledgeWorkspaceRepository(db)
    await repo.require_base(uid, kb_id)
    return [folder_data(row) for row in await repo.folders(kb_id)]


async def save_folder(db, uid, kb_id, payload, folder_id=None):
    repo = KnowledgeWorkspaceRepository(db)
    await repo.require_base(uid, kb_id, lock=True)
    await repo.folder(kb_id, payload.parent_id)
    folders = await repo.folders(kb_id)
    if any(row.name == payload.name and row.parent_id == payload.parent_id and row.folder_id != folder_id for row in folders):
        raise ValueError('此目录下已有同名文件夹')
    row = await repo.folder(kb_id, folder_id)
    if row:
        parent = payload.parent_id
        by_id = {item.folder_id: item for item in folders}
        while parent:
            if parent == folder_id:
                raise ValueError('不能将文件夹移动到自身或子目录')
            parent = by_id[parent].parent_id
        row.name, row.parent_id = payload.name, payload.parent_id
    else:
        row = KnowledgeFolder(folder_id=uuid4().hex, kb_id=kb_id, name=payload.name, parent_id=payload.parent_id)
        db.add(row)
    await db.commit()
    return folder_data(row)


async def delete_folder(db, uid, kb_id, folder_id):
    repo = KnowledgeWorkspaceRepository(db)
    await repo.require_base(uid, kb_id, lock=True)
    row = await repo.folder(kb_id, folder_id)
    if any(item.parent_id == folder_id for item in await repo.folders(kb_id)) or await repo.folder_has_files(kb_id, folder_id):
        raise ValueError('请先移走或删除文件夹中的内容')
    await db.delete(row)
    await db.commit()
    return {'folder_id': folder_id}


async def update_file(db, uid, kb_id, file_id, payload):
    repo = KnowledgeWorkspaceRepository(db)
    await repo.require_base(uid, kb_id, lock=True)
    await repo.folder(kb_id, payload.folder_id)
    row = (await repo.files(kb_id, [file_id]))[0]
    if row.status in {'parsing', 'indexing', 'extracting'}:
        raise ValueError('文件正在处理中')
    # 对象键和索引 ID 保持稳定；展示名称由 PostgreSQL 元数据拥有。
    row.original_file_name, row.folder_id = payload.name, payload.folder_id
    await db.commit()
    return {'file_id': file_id}


async def list_tasks(db, uid, kb_id):
    repo = KnowledgeWorkspaceRepository(db)
    await repo.require_base(uid, kb_id)
    return [task_data(row) for row in await repo.tasks(uid, kb_id)]


async def create_task(db, uid, kb_id, operation, payload):
    repo = KnowledgeWorkspaceRepository(db)
    await repo.require_base(uid, kb_id, lock=True)
    file_ids = payload.get('file_ids', [])
    if file_ids:
        await repo.files(kb_id, file_ids)
        for task in await repo.tasks(uid, kb_id, active=True):
            if set(task.payload.get('file_ids', [])) & set(file_ids):
                raise ValueError('选中文件已有未完成的处理任务')
    if operation == 'evaluate':
        dataset = RetrievalDataset.from_dict({**payload, 'uid': uid, 'kb_id': kb_id})
        RetrievalEvaluator(retrieve=lambda *_: None, ks=payload['ks'])
        # 所有人工标注必须来自当前库，防止以别库 Chunk ID 产生误导性报告。
        await repo.files(kb_id, list({chunk.rsplit(':', 1)[0] for sample in dataset.samples for chunk in sample.relevant_chunk_ids}))
    row = KnowledgeTask(task_id=uuid4().hex, kb_id=kb_id, uid=uid, operation=operation, payload=payload, status='pending', results=[])
    db.add(row)
    await db.commit()
    try:
        pool = await get_arq_pool()
        await pool.enqueue_job('process_knowledge_task', row.task_id, _job_id=f'knowledge:{row.task_id}', _queue_name=config.arq_queue_name)
    except Exception as exc:
        row.status, row.error, row.finished_at = 'failed', str(exc), datetime.now(UTC)
        await db.commit()
        raise
    return task_data(row)


async def cancel_task(db, uid, kb_id, task_id):
    repo = KnowledgeWorkspaceRepository(db)
    await repo.require_base(uid, kb_id)
    row = await repo.task(task_id, lock=True)
    if row.kb_id != kb_id or row.uid != uid:
        raise LookupError('任务不存在')
    if row.status in {'pending', 'running'}:
        row.status, row.finished_at = 'cancelled', datetime.now(UTC)
        await db.commit()
    return task_data(row)


async def _append_result(task_id, result):
    async with session_context() as db:
        row = await KnowledgeWorkspaceRepository(db).task(task_id, lock=True)
        row.results = [*row.results, result]
        await db.commit()


async def _is_cancelled(task_id):
    async with session_context() as db:
        return (await KnowledgeWorkspaceRepository(db).task(task_id)).status == 'cancelled'


async def process_knowledge_task(ctx, task_id):
    """每个文件独立提交结果；浏览器关闭不取消后台任务。"""
    async with session_context() as db:
        row = await KnowledgeWorkspaceRepository(db).task(task_id, lock=True)
        if row.status != 'pending':
            return
        uid, kb_id, operation, payload = row.uid, row.kb_id, row.operation, dict(row.payload)
        row.status = 'running'
        await db.commit()
    report, error = None, None
    try:
        if operation == 'evaluate':
            async def retrieve(query, limit):
                if await _is_cancelled(task_id):
                    raise asyncio.CancelledError()
                async with session_context() as db:
                    result = await knowledge_service.search_chunks(db, uid=uid, kb_id=kb_id, query=query, limit=limit)
                await _append_result(task_id, {'query': query, 'success': True, 'hit_count': len(result['hits'])})
                return result['hits']
            dataset = RetrievalDataset.from_dict({**payload, 'uid': uid, 'kb_id': kb_id})
            report = (await RetrievalEvaluator(retrieve=retrieve, ks=payload['ks']).evaluate(dataset)).to_dict()
        else:
            operation_fn = {'parse': knowledge_service.parse_file, 'index': knowledge_service.index_file, 'extract': knowledge_service.extract_file, 'delete': knowledge_service.delete_file}[operation]
            for file_id in payload['file_ids']:
                if await _is_cancelled(task_id):
                    break
                try:
                    async with session_context() as db:
                        await operation_fn(db, uid=uid, kb_id=kb_id, file_id=file_id)
                    result = {'file_id': file_id, 'success': True}
                except Exception as exc:
                    result = {'file_id': file_id, 'success': False, 'error': str(exc)}
                await _append_result(task_id, result)
    except asyncio.CancelledError:
        error = '任务执行被中断'
        raise
    except Exception as exc:
        error = str(exc)
    finally:
        async with session_context() as db:
            row = await KnowledgeWorkspaceRepository(db).task(task_id, lock=True)
            if row.status != 'cancelled':
                row.status = 'failed' if error or any(not item['success'] for item in row.results) else 'completed'
                row.error, row.report, row.finished_at = error, report, datetime.now(UTC)
                await db.commit()
