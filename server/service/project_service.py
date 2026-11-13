from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Project
from src.database.repositories import ProjectRepository


def project_response(project: Project) -> dict:
    return {
        "project_id": str(project.project_id),
        "name": project.name,
        "pinned": project.pinned_at is not None,
        "pinned_at": project.pinned_at,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


async def list_projects(db: AsyncSession, *, uid: str) -> list[dict]:
    return [project_response(project) for project in await ProjectRepository(db).list_for_user(uid)]


async def create_project(db: AsyncSession, *, uid: str, name: str) -> dict:
    return project_response(await ProjectRepository(db).create(uid, name))


async def update_project(db: AsyncSession, *, uid: str, project_id: str, fields: dict) -> dict:
    if not fields:
        raise ValueError("未提供可更新的项目字段")
    repository = ProjectRepository(db)
    project = await repository.require_for_user(uid, project_id, for_update=True)
    return project_response(await repository.update(project, fields))


async def delete_project(db: AsyncSession, *, uid: str, project_id: str) -> None:
    repository = ProjectRepository(db)
    project = await repository.require_for_user(uid, project_id, for_update=True)
    await repository.soft_delete(project)
