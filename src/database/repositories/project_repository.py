from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Conversation, Project


class ProjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_user(self, uid: str) -> list[Project]:
        result = await self.session.execute(
            select(Project).where(Project.uid == uid, Project.deleted_at.is_(None))
            .order_by(Project.pinned_at.desc().nulls_last(), Project.updated_at.desc(), Project.id.desc())
        )
        return list(result.scalars().all())

    async def require_for_user(self, uid: str, project_id: str, *, for_update: bool = False) -> Project:
        statement = select(Project).where(
            Project.project_id == project_id, Project.uid == uid, Project.deleted_at.is_(None),
        )
        if for_update:
            # 绑定与删除持有同一 Project 行锁，避免删除事务漏掉并发新增的归属。
            statement = statement.with_for_update().execution_options(populate_existing=True)
        project = (await self.session.execute(statement)).scalar_one_or_none()
        if project is None:
            raise LookupError("项目不存在或已删除")
        return project

    async def create(self, uid: str, name: str, *, project_id: str | None = None) -> Project:
        project = Project(uid=uid, name=name, project_id=project_id or str(uuid4()))
        self.session.add(project)
        await self.session.flush()
        return project

    async def update(self, project: Project, fields: dict) -> Project:
        if "name" in fields:
            project.name = fields["name"]
        if "pinned" in fields:
            project.pinned_at = datetime.now(UTC) if fields["pinned"] else None
        project.updated_at = datetime.now(UTC)
        await self.session.flush()
        return project

    async def soft_delete(self, project: Project) -> None:
        project.deleted_at = project.updated_at = datetime.now(UTC)
        await self.session.execute(
            update(Conversation).where(
                Conversation.uid == project.uid,
                Conversation.project_id == project.project_id,
                Conversation.deleted_at.is_(None),
            ).values(project_id=None)
        )
        await self.session.flush()
