"""知识库向量记录 API。"""

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from server.entities.knowledge import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseResponse,
    KnowledgeDeleteRequest,
    KnowledgeFileResponse,
    KnowledgeIndexResponse,
    KnowledgeSearchRequest,
)
from server.service.knowledge_service import KnowledgeService
from server.utils.auth import AuthenticatedUser
from src.database import get_db

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.post("/bases", response_model=KnowledgeBaseResponse)
async def create_knowledge_base(
    payload: KnowledgeBaseCreateRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """创建当前用户的逻辑知识库。"""
    knowledge_base = await KnowledgeService(db).create_knowledge_base(
        uid=current_user.uid,
        name=payload.name,
        description=payload.description,
    )
    return KnowledgeBaseResponse(
        kb_id=knowledge_base.kb_id,
        name=knowledge_base.name,
        description=knowledge_base.description,
        status=knowledge_base.status,
    )


@router.get("/bases/{kb_id}/files", response_model=list[str])
async def list_knowledge_files(
    kb_id: str,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """列出当前用户知识库中的原始文件名。"""
    try:
        return await KnowledgeService(db).list_file_names(
            uid=current_user.uid,
            kb_id=kb_id,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/bases/{kb_id}/files", response_model=KnowledgeFileResponse)
async def upload_knowledge_file(
    kb_id: str,
    current_user: AuthenticatedUser,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """上传知识库原文件，不触发解析和索引。"""
    try:
        content = await file.read()
        knowledge_file = await KnowledgeService(db).upload_file(
            uid=current_user.uid,
            kb_id=kb_id,
            file_name=file.filename or "file",
            content=content,
            content_type=file.content_type,
        )
        return _knowledge_file_response(knowledge_file)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/bases/{kb_id}/files/{file_id}/parse",
    response_model=KnowledgeFileResponse,
)
async def parse_knowledge_file(
    kb_id: str,
    file_id: str,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """解析原文件并保存 Markdown，等待用户确认索引。"""
    try:
        knowledge_file = await KnowledgeService(db).parse_file(
            uid=current_user.uid,
            kb_id=kb_id,
            file_id=file_id,
        )
        return _knowledge_file_response(knowledge_file)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/bases/{kb_id}/files/{file_id}/index",
    response_model=KnowledgeIndexResponse,
)
async def index_knowledge_file(
    kb_id: str,
    file_id: str,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
) -> KnowledgeIndexResponse:
    """确认解析结果后执行分块、向量化和 Milvus 入库。"""
    try:
        result = await KnowledgeService(db).index_file(
            uid=current_user.uid,
            kb_id=kb_id,
            file_id=file_id,
        )
        return KnowledgeIndexResponse(**result)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post("/{knowledge_type}/search")
async def search_knowledge_records(
    knowledge_type: str,
    payload: KnowledgeSearchRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """按知识库绑定模型执行向量检索。"""
    try:
        return await KnowledgeService(db, knowledge_type).search(
            uid=current_user.uid,
            kb_id=payload.kb_id,
            query=payload.query,
            limit=payload.limit,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.delete("/{knowledge_type}/records")
async def delete_knowledge_records(
    knowledge_type: str,
    payload: KnowledgeDeleteRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """删除绑定知识库中的指定记录。"""
    try:
        return await KnowledgeService(db, knowledge_type).delete_records(
            uid=current_user.uid,
            kb_id=payload.kb_id,
            record_ids=payload.record_ids,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get("/{knowledge_type}/status")
async def get_knowledge_status(
    knowledge_type: str,
    current_user: AuthenticatedUser,
    kb_id: str = Query(min_length=1, max_length=128),
    db: AsyncSession = Depends(get_db),
):
    """读取当前用户绑定知识库的集合状态。"""
    try:
        return await KnowledgeService(db, knowledge_type).status(
            uid=current_user.uid,
            kb_id=kb_id,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


def _knowledge_file_response(knowledge_file) -> KnowledgeFileResponse:
    """将知识文件模型转换为 API 响应。"""
    return KnowledgeFileResponse(
        file_id=knowledge_file.file_id,
        kb_id=knowledge_file.kb_id,
        original_file_name=knowledge_file.original_file_name,
        original_object_name=knowledge_file.original_object_name,
        markdown_object_name=knowledge_file.markdown_object_name,
        content_type=knowledge_file.content_type,
        file_size=knowledge_file.file_size,
        status=knowledge_file.status,
        error_message=knowledge_file.error_message,
    )
