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
    KnowledgeBaseDeleteResponse,
    KnowledgeBaseResponse,
    KnowledgeChatRequest,
    KnowledgeChatResponse,
    KnowledgeDeleteRequest,
    KnowledgeEntitySearchRequest,
    KnowledgeEntitySearchResponse,
    KnowledgeExtractResponse,
    KnowledgeFileDeleteResponse,
    KnowledgeFileMarkdownResponse,
    KnowledgeFileResponse,
    KnowledgeGraphResponse,
    KnowledgeIndexResponse,
    KnowledgeSearchRequest,
)
from server.service import knowledge_service
from server.utils.auth import AuthenticatedUser
from src.database import get_db

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/bases", response_model=KnowledgeBaseResponse)
async def create_knowledge_base(
    payload: KnowledgeBaseCreateRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """创建当前用户的逻辑知识库。"""
    knowledge_base = await knowledge_service.create_knowledge_base(
        db,
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


@router.get("/bases", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户的全部知识库。"""
    knowledge_bases = await knowledge_service.list_knowledge_bases(
        db,
        uid=current_user.uid,
    )
    return [
        KnowledgeBaseResponse(
            kb_id=item.kb_id,
            name=item.name,
            description=item.description,
            status=item.status,
        )
        for item in knowledge_bases
    ]


@router.get("/bases/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: str,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """读取当前用户的指定知识库。"""
    try:
        knowledge_base = await knowledge_service.get_knowledge_base(
            db,
            uid=current_user.uid,
            kb_id=kb_id,
        )
        return KnowledgeBaseResponse(
            kb_id=knowledge_base.kb_id,
            name=knowledge_base.name,
            description=knowledge_base.description,
            status=knowledge_base.status,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.delete("/bases/{kb_id}", response_model=KnowledgeBaseDeleteResponse)
async def delete_knowledge_base(
    kb_id: str,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """删除知识库及其全部文件、向量与图谱数据。"""
    try:
        result = await knowledge_service.delete_knowledge_base(
            db,
            uid=current_user.uid,
            kb_id=kb_id,
        )
        return KnowledgeBaseDeleteResponse(**result)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("/bases/{kb_id}/files", response_model=list[KnowledgeFileResponse])
async def list_knowledge_files(
    kb_id: str,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户知识库中的全部文件。"""
    try:
        knowledge_files = await knowledge_service.list_files(
            db,
            uid=current_user.uid,
            kb_id=kb_id,
        )
        return [
            _knowledge_file_response(item) for item in knowledge_files
        ]
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
        knowledge_file = await knowledge_service.upload_file(
            db,
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
        knowledge_file = await knowledge_service.parse_file(
            db,
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
        result = await knowledge_service.index_file(
            db,
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


@router.delete(
    "/bases/{kb_id}/files/{file_id}",
    response_model=KnowledgeFileDeleteResponse,
)
async def delete_knowledge_file(
    kb_id: str,
    file_id: str,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """删除知识文件及其解析、索引与图谱数据。"""
    try:
        result = await knowledge_service.delete_file(
            db,
            uid=current_user.uid,
            kb_id=kb_id,
            file_id=file_id,
        )
        return KnowledgeFileDeleteResponse(**result)
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


@router.get(
    "/bases/{kb_id}/files/{file_id}/markdown",
    response_model=KnowledgeFileMarkdownResponse,
)
async def get_knowledge_file_markdown(
    kb_id: str,
    file_id: str,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """读取知识文件已解析的 Markdown 产物。"""
    try:
        result = await knowledge_service.get_file_markdown(
            db,
            uid=current_user.uid,
            kb_id=kb_id,
            file_id=file_id,
        )
        return KnowledgeFileMarkdownResponse(**result)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/bases/{kb_id}/files/{file_id}/extract",
    response_model=KnowledgeExtractResponse,
)
async def extract_knowledge_file(
    kb_id: str,
    file_id: str,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """抽取文件实体关系并写入 Neo4j 与 Milvus 实体集合。"""
    try:
        result = await knowledge_service.extract_file(
            db,
            uid=current_user.uid,
            kb_id=kb_id,
            file_id=file_id,
        )
        return KnowledgeExtractResponse(**result)
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


@router.get(
    "/bases/{kb_id}/graph",
    response_model=KnowledgeGraphResponse,
)
async def get_knowledge_graph(
    kb_id: str,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """读取知识库全量实体与关系图谱。"""
    try:
        result = await knowledge_service.get_graph(
            db,
            uid=current_user.uid,
            kb_id=kb_id,
        )
        return KnowledgeGraphResponse(**result)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/bases/{kb_id}/entities/search",
    response_model=KnowledgeEntitySearchResponse,
)
async def search_knowledge_entities(
    kb_id: str,
    payload: KnowledgeEntitySearchRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """使用实体向量检索知识库实体。"""
    try:
        result = await knowledge_service.search_entities(
            db,
            uid=current_user.uid,
            kb_id=kb_id,
            query=payload.query,
            limit=payload.limit,
        )
        return KnowledgeEntitySearchResponse(**result)
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
    "/bases/{kb_id}/chat",
    response_model=KnowledgeChatResponse,
)
async def chat_with_knowledge_base(
    kb_id: str,
    payload: KnowledgeChatRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """基于知识库检索结果同步生成带引用的回答。"""
    try:
        result = await knowledge_service.chat(
            db,
            uid=current_user.uid,
            kb_id=kb_id,
            query=payload.query,
            limit=payload.limit,
        )
        return KnowledgeChatResponse(**result)
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
        return await knowledge_service.search(
            db,
            uid=current_user.uid,
            kb_id=payload.kb_id,
            query=payload.query,
            limit=payload.limit,
            knowledge_type=knowledge_type,
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
        return await knowledge_service.delete_records(
            db,
            uid=current_user.uid,
            kb_id=payload.kb_id,
            record_ids=payload.record_ids,
            knowledge_type=knowledge_type,
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
        return await knowledge_service.status(
            db,
            uid=current_user.uid,
            kb_id=kb_id,
            knowledge_type=knowledge_type,
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
