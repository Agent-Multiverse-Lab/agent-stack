"""知识库工作区 HTTP 接口。"""

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from server.entities.knowledge_workspace import KnowledgeBaseUpdate, KnowledgeEvaluationCreate, KnowledgeFileUpdate, KnowledgeFolderCreate, KnowledgeTaskCreate
from server.service import knowledge_workspace_service as workspace
from server.utils.auth import AuthenticatedUser
from src.database import get_db
from src.database.repositories.knowledge_repository import KnowledgeFileRepository
from src.storage.minio import get_storage

router = APIRouter(prefix='/knowledge/bases/{kb_id}', tags=['knowledge'])


async def respond(operation):
    try:
        return await operation
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get('/settings')
async def settings(kb_id: str, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return await respond(workspace.get_settings(db, current_user.uid, kb_id))


@router.post('/settings')
async def save_settings(kb_id: str, payload: KnowledgeBaseUpdate, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return await respond(workspace.update_settings(db, current_user.uid, kb_id, payload))


@router.get('/folders')
async def folders(kb_id: str, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return await respond(workspace.list_folders(db, current_user.uid, kb_id))


@router.post('/folders')
async def create_folder(kb_id: str, payload: KnowledgeFolderCreate, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return await respond(workspace.save_folder(db, current_user.uid, kb_id, payload))


@router.post('/folders/{folder_id}')
async def update_folder(kb_id: str, folder_id: str, payload: KnowledgeFolderCreate, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return await respond(workspace.save_folder(db, current_user.uid, kb_id, payload, folder_id))


@router.delete('/folders/{folder_id}')
async def delete_folder(kb_id: str, folder_id: str, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return await respond(workspace.delete_folder(db, current_user.uid, kb_id, folder_id))


@router.post('/files/{file_id}/metadata')
async def update_file(kb_id: str, file_id: str, payload: KnowledgeFileUpdate, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return await respond(workspace.update_file(db, current_user.uid, kb_id, file_id, payload))


@router.get('/files/{file_id}/download')
async def download_file(kb_id: str, file_id: str, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    row = await KnowledgeFileRepository(db).get_for_user(uid=current_user.uid, kb_id=kb_id, file_id=file_id)
    if row is None:
        raise HTTPException(404, '文件不存在')
    content = await get_storage().adownload_file('knowledgebases', row.original_object_name)
    return Response(content, media_type=row.content_type, headers={'Content-Disposition': "attachment; filename*=UTF-8''" + quote(row.original_file_name, safe='')})


@router.get('/tasks')
async def tasks(kb_id: str, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return await respond(workspace.list_tasks(db, current_user.uid, kb_id))


@router.post('/tasks')
async def create_task(kb_id: str, payload: KnowledgeTaskCreate, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return await respond(workspace.create_task(db, current_user.uid, kb_id, payload.operation, payload.model_dump()))


@router.post('/tasks/{task_id}/cancel')
async def cancel_task(kb_id: str, task_id: str, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return await respond(workspace.cancel_task(db, current_user.uid, kb_id, task_id))


@router.post('/evaluations')
async def evaluate(kb_id: str, payload: KnowledgeEvaluationCreate, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return await respond(workspace.create_task(db, current_user.uid, kb_id, 'evaluate', payload.model_dump()))
