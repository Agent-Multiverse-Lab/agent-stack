"""知识库目录和任务的 PostgreSQL 读写。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import KnowledgeBase, KnowledgeFile, KnowledgeFolder, KnowledgeTask


class KnowledgeWorkspaceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def require_base(self, uid: str, kb_id: str, *, lock: bool = False):
        statement = select(KnowledgeBase).where(KnowledgeBase.kb_id == kb_id, KnowledgeBase.uid == uid)
        if lock:
            statement = statement.with_for_update()
        base = (await self.session.execute(statement)).scalar_one_or_none()
        if base is None:
            raise LookupError('知识库不存在')
        return base

    async def folders(self, kb_id: str):
        return list((await self.session.scalars(select(KnowledgeFolder).where(KnowledgeFolder.kb_id == kb_id).order_by(KnowledgeFolder.name))).all())

    async def folder(self, kb_id: str, folder_id: str | None):
        if folder_id is None:
            return None
        row = (await self.session.scalars(select(KnowledgeFolder).where(KnowledgeFolder.kb_id == kb_id, KnowledgeFolder.folder_id == folder_id))).one_or_none()
        if row is None:
            raise LookupError('文件夹不存在')
        return row

    async def files(self, kb_id: str, file_ids: list[str]):
        rows = list((await self.session.scalars(select(KnowledgeFile).where(KnowledgeFile.kb_id == kb_id, KnowledgeFile.file_id.in_(file_ids)))).all())
        if len(rows) != len(file_ids):
            raise LookupError('文件不存在或不属于当前知识库')
        return rows

    async def folder_has_files(self, kb_id: str, folder_id: str) -> bool:
        return (await self.session.scalars(select(KnowledgeFile.file_id).where(KnowledgeFile.kb_id == kb_id, KnowledgeFile.folder_id == folder_id).limit(1))).first() is not None

    async def tasks(self, uid: str, kb_id: str, *, active: bool = False):
        statement = select(KnowledgeTask).where(KnowledgeTask.uid == uid, KnowledgeTask.kb_id == kb_id)
        if active:
            statement = statement.where(KnowledgeTask.status.in_(['pending', 'running']))
        else:
            statement = statement.order_by(KnowledgeTask.created_at.desc()).limit(100)
        return list((await self.session.scalars(statement)).all())

    async def task(self, task_id: str, *, lock: bool = False):
        statement = select(KnowledgeTask).where(KnowledgeTask.task_id == task_id)
        if lock:
            statement = statement.with_for_update()
        row = (await self.session.scalars(statement)).one_or_none()
        if row is None:
            raise LookupError('任务不存在')
        return row
