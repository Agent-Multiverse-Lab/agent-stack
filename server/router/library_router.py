from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from server.entities.library import KnowledgeItem
from server.utils.auth import AuthenticatedUser
from src.database import get_db
from src.database.models import Knowledge
from src.database.repositories import KnowledgeRepository

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _knowledge_response(item: Knowledge) -> KnowledgeItem:
    return KnowledgeItem(
        id=str(item.id),
        kind=item.kind,
        title=item.title,
        summary=item.summary,
        content_text=item.content_text,
        file_name=item.file_name,
        path=item.path,
        minio_url=item.minio_url,
        markdown_file=item.markdown_file,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


@router.get("", response_model=list[KnowledgeItem])
async def list_knowledge(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    items = await KnowledgeRepository(db).list_for_user(user_id=current_user.id)
    return [_knowledge_response(item) for item in items]
