from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from server.entities.project import ProjectRequest, ProjectResponse, ProjectUpdateRequest
from server.service import project_service
from server.utils.auth import AuthenticatedUser
from src.database import get_db

router = APIRouter(prefix="/projects", tags=["会话项目"])


@router.post("", response_model=ProjectResponse)
async def create_project(payload: ProjectRequest, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return await project_service.create_project(db, uid=current_user.uid, name=payload.name)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    return await project_service.list_projects(db, uid=current_user.uid)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str, payload: ProjectUpdateRequest,
    current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db),
):
    try:
        return await project_service.update_project(
            db, uid=current_user.uid, project_id=project_id, fields=payload.model_dump(exclude_unset=True),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, current_user: AuthenticatedUser, db: AsyncSession = Depends(get_db)):
    try:
        await project_service.delete_project(db, uid=current_user.uid, project_id=project_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)
