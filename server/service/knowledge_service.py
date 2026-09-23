"""知识库向量化、检索重排与存储用例。"""

from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Any
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from src.configs import config as sys_config
from src.database.models import (
    KnowledgeBase,
    KnowledgeEmbeddingBinding,
    KnowledgeFile,
)
from src.database.repositories import (
    KnowledgeBaseRepository,
    KnowledgeEmbeddingBindingRepository,
    KnowledgeFileRepository,
)
from src.knowledge.base import KnowledgeRecord
from src.knowledge.embedding_service import EmbeddingService
from src.knowledge.factory import KnowledgeFactory
from src.knowledge.flow import Pipeline
from src.knowledge.graph import GraphExtractor
from src.knowledge.store.milvus.milvus import MilvusKnowledge
from src.knowledge.store.neo4j.neo4j_store import get_graph_store
from src.model import (
    RerankDocument,
    load_embedding_model,
    load_model,
    load_reranker,
    resolve_embedding_model,
)
from src.storage.minio import get_storage, sanitize_filename
from src.utils import logger

_KNOWLEDGE_BUCKET = "knowledgebases"
_ENTITY_COLLECTION_PREFIX = "kge_"
_ENTITY_DEDUPE_THRESHOLD = 0.92
_EXTRACT_MAX_CHARS = 60_000
_CITATION_EXCERPT_CHARS = 300

_CHAT_SYSTEM_PROMPT = (
    "你是知识库问答助手。只能根据提供的检索片段回答用户问题，"
    "禁止编造片段中没有的信息。回答使用中文，条理清晰。"
    "引用片段内容时，在相关句末标注片段编号，例如[1]、[2]。"
    "如果片段信息不足以回答，请明确说明。"
)
_CHAT_NO_ANSWER = "知识库中未找到与问题相关的内容。"


async def create_knowledge_base(
    db: AsyncSession,
    *,
    uid: str,
    name: str,
    description: str = "",
) -> KnowledgeBase:
    """创建用户知识库。"""
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("知识库名称不能为空")

    knowledge_base = await KnowledgeBaseRepository(db).create(
        kb_id=uuid4().hex,
        uid=uid,
        name=normalized_name,
        description=description.strip(),
    )
    await db.commit()
    return knowledge_base


async def upload_file(
    db: AsyncSession,
    *,
    uid: str,
    kb_id: str,
    file_name: str,
    content: bytes,
    content_type: str | None = None,
) -> KnowledgeFile:
    """上传知识库原文件并创建独立文件记录。"""
    knowledge_base = await KnowledgeBaseRepository(db).get_for_user(
        uid=uid,
        kb_id=kb_id,
    )
    if knowledge_base is None:
        raise LookupError(f"知识库不存在：{kb_id}")
    if not content:
        raise ValueError("知识文件内容不能为空")

    normalized_name = sanitize_filename(file_name)
    file_id = uuid4().hex
    root = f"knowledge-files/{uid}/{kb_id}/{file_id}"
    original_object_name = f"{root}/original/{normalized_name}"
    storage = get_storage()

    await storage.aupload_file(
        _KNOWLEDGE_BUCKET,
        original_object_name,
        content,
        content_type or "application/octet-stream",
    )
    try:
        knowledge_file = await KnowledgeFileRepository(db).create(
            file_id=file_id,
            kb_id=kb_id,
            original_file_name=file_name,
            original_object_name=original_object_name,
            content_type=content_type or "application/octet-stream",
            file_size=len(content),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        await storage.adelete_file(
            _KNOWLEDGE_BUCKET,
            original_object_name,
        )
        raise
    return knowledge_file


async def parse_file(
    db: AsyncSession,
    *,
    uid: str,
    kb_id: str,
    file_id: str,
) -> KnowledgeFile:
    """解析知识文件并将 Markdown 保存到 RustFS。"""
    knowledge_files = KnowledgeFileRepository(db)
    knowledge_file = await knowledge_files.get_for_user(
        uid=uid,
        kb_id=kb_id,
        file_id=file_id,
    )
    if knowledge_file is None:
        raise LookupError(f"知识文件不存在：{file_id}")
    if knowledge_file.status == "parsed":
        return knowledge_file
    if knowledge_file.status not in {"uploaded", "failed"}:
        raise ValueError(
            f"知识文件当前状态不允许解析：{knowledge_file.status}"
        )

    await knowledge_files.update_status(
        knowledge_file,
        status="parsing",
    )
    await db.commit()

    markdown_object_name = (
        f"knowledge-files/{uid}/{kb_id}/{file_id}/parsed/document.md"
    )
    storage = get_storage()
    pipeline = Pipeline()
    try:
        content = await storage.adownload_file(
            _KNOWLEDGE_BUCKET,
            knowledge_file.original_object_name,
        )
        document = await pipeline.parse_document(
            content,
            file_name=knowledge_file.original_file_name,
        )
        if not document.markdown.strip():
            raise ValueError("Parser 未生成有效 Markdown")

        await storage.aupload_file(
            _KNOWLEDGE_BUCKET,
            markdown_object_name,
            document.markdown.encode(),
            "text/markdown",
        )
        await knowledge_files.update_status(
            knowledge_file,
            status="parsed",
            markdown_object_name=markdown_object_name,
        )
        await db.commit()
        return knowledge_file
    except Exception as exc:
        await db.rollback()
        knowledge_file = await knowledge_files.get_for_user(
            uid=uid,
            kb_id=kb_id,
            file_id=file_id,
        )
        if knowledge_file is not None:
            await knowledge_files.update_status(
                knowledge_file,
                status="failed",
                error_message=str(exc)[:2000],
            )
            await db.commit()
        raise


async def index_file(
    db: AsyncSession,
    *,
    uid: str,
    kb_id: str,
    file_id: str,
) -> dict[str, Any]:
    """将用户确认后的 Markdown 分块、向量化并写入 Milvus。"""
    knowledge_files = KnowledgeFileRepository(db)
    bindings = KnowledgeEmbeddingBindingRepository(db)
    file_record = await knowledge_files.get_for_user(
        uid=uid,
        kb_id=kb_id,
        file_id=file_id,
    )
    if file_record is None:
        raise LookupError("知识库文件不存在")
    if file_record.status != "parsed":
        raise ValueError("只有 parsed 状态的文件可以执行索引")
    if not file_record.markdown_object_name:
        raise ValueError("知识库文件缺少已解析的 Markdown")

    await knowledge_files.update_status(
        file_record,
        status="indexing",
        error_message=None,
    )
    await db.commit()

    storage = get_storage()
    pipeline = Pipeline()
    try:
        markdown = await storage.adownload_file(
            _KNOWLEDGE_BUCKET,
            file_record.markdown_object_name,
        )
        document = await pipeline.parse_document(
            markdown,
            file_name="document.md",
        )
        chunks = pipeline.chunk_document(document)
        if not chunks:
            raise ValueError("Markdown 分块结果不能为空")

        records = []
        for chunk_index, chunk in enumerate(chunks):
            chunk_id = f"{file_id}:{chunk_index}"
            records.append(
                {
                    "id": chunk_id,
                    "content": chunk.text,
                    "metadata": {
                        **chunk.metadata,
                        "uid": uid,
                        "kb_id": kb_id,
                        "file_id": file_id,
                        "file_name": file_record.original_file_name,
                        "chunk_id": chunk_id,
                        "chunk_index": chunk_index,
                    },
                }
            )

        binding = await bindings.get(uid=uid, kb_id=kb_id)
        binding_created = binding is None
        embedding, resolved_spec, batch_size = _create_embedding_service(
            binding.embedding_model_spec if binding is not None else None,
            expected_dimension=(
                binding.embedding_dimension if binding is not None else None
            ),
            batch_size=(
                binding.embedding_batch_size if binding is not None else None
            ),
        )
        contents = [record["content"].strip() for record in records]
        vectors = await embedding.embed_texts(contents)
        dimension = embedding.dimension
        if dimension is None:
            raise RuntimeError("Embedding 模型未返回向量维度")

        if binding is None:
            binding = await bindings.create(
                uid=uid,
                kb_id=kb_id,
                collection_name=_collection_name(uid, kb_id),
                embedding_model_spec=resolved_spec,
                embedding_dimension=dimension,
                embedding_batch_size=batch_size,
            )

        knowledge_records = [
            KnowledgeRecord(
                id=record["id"],
                content=content,
                vector=vector,
                metadata=record["metadata"],
            )
            for record, content, vector in zip(
                records,
                contents,
                vectors,
                strict=True,
            )
        ]
        await _get_knowledge("milvus").build_file_index(
            collection_name=binding.collection_name,
            file_id=file_id,
            dimension=binding.embedding_dimension,
            records=knowledge_records,
        )
        if binding_created:
            await db.commit()

        await knowledge_files.update_status(
            file_record,
            status="indexed",
            error_message=None,
        )
        await db.commit()
        return {
            "kb_id": kb_id,
            "file_id": file_id,
            "status": "indexed",
            "chunk_count": len(chunks),
            "collection_name": binding.collection_name,
            "embedding_model_spec": binding.embedding_model_spec,
            "embedding_dimension": binding.embedding_dimension,
        }
    except Exception as exc:
        await db.rollback()
        file_record = await knowledge_files.get_for_user(
            uid=uid,
            kb_id=kb_id,
            file_id=file_id,
        )
        if file_record is not None:
            await knowledge_files.update_status(
                file_record,
                status="parsed",
                error_message=str(exc),
            )
            await db.commit()
        raise


async def search(
    db: AsyncSession,
    *,
    uid: str,
    kb_id: str,
    query: str,
    limit: int,
    knowledge_type: str = "milvus",
) -> dict[str, Any]:
    """使用绑定 Embedding 初召回，并按配置执行查询时重排。"""
    if limit <= 0:
        raise ValueError("知识库检索 limit 必须大于 0")

    binding = await _require_binding(db, uid, kb_id)
    embedding, _, _ = _create_embedding_service(
        binding.embedding_model_spec,
        expected_dimension=binding.embedding_dimension,
        batch_size=binding.embedding_batch_size,
    )
    vector = await embedding.embed_query(query)
    rerank_model_spec = sys_config.rerank_model.strip()
    candidate_limit = (
        max(limit, sys_config.rerank_candidate_limit)
        if rerank_model_spec
        else limit
    )
    hits = await _get_knowledge(knowledge_type).search(
        collection_name=binding.collection_name,
        vector=vector,
        limit=candidate_limit,
    )
    if not rerank_model_spec:
        return _binding_result(binding, hits=hits)
    if not hits:
        return _binding_result(
            binding,
            hits=[],
            rerank={
                "applied": False,
                "model_spec": rerank_model_spec,
                "candidate_count": 0,
                "result_count": 0,
            },
        )

    try:
        reranked_hits = await _rerank_hits(
            query=query,
            hits=hits,
            limit=limit,
        )
    except Exception:
        logger.exception(
            "知识库 Rerank 失败：uid=%s kb_id=%s model=%s "
            "candidate_count=%s",
            uid,
            kb_id,
            rerank_model_spec,
            len(hits),
        )
        raise

    return _binding_result(
        binding,
        hits=reranked_hits,
        rerank={
            "applied": True,
            "model_spec": rerank_model_spec,
            "candidate_count": len(hits),
            "result_count": len(reranked_hits),
        },
    )


async def delete_records(
    db: AsyncSession,
    *,
    uid: str,
    kb_id: str,
    record_ids: Sequence[str],
    knowledge_type: str = "milvus",
) -> dict[str, Any]:
    """删除用户知识库中的指定向量记录。"""
    if not record_ids:
        raise ValueError("待删除记录 ID 不能为空")

    binding = await _require_binding(db, uid, kb_id)
    result = await _get_knowledge(knowledge_type).delete(
        collection_name=binding.collection_name,
        record_ids=record_ids,
    )
    return _binding_result(binding, result=result)


async def status(
    db: AsyncSession,
    *,
    uid: str,
    kb_id: str,
    knowledge_type: str = "milvus",
) -> dict[str, Any]:
    """读取绑定知识库对应 Milvus 集合的状态。"""
    binding = await _require_binding(db, uid, kb_id)
    result = await _get_knowledge(knowledge_type).status(
        collection_name=binding.collection_name
    )
    return _binding_result(binding, status=result)


async def list_knowledge_bases(
    db: AsyncSession,
    *,
    uid: str,
) -> list[KnowledgeBase]:
    """列出当前用户的全部知识库。"""
    return await KnowledgeBaseRepository(db).list_for_user(uid=uid)


async def get_knowledge_base(
    db: AsyncSession,
    *,
    uid: str,
    kb_id: str,
) -> KnowledgeBase:
    """读取属于当前用户的指定知识库。"""
    knowledge_base = await KnowledgeBaseRepository(db).get_for_user(
        uid=uid,
        kb_id=kb_id,
    )
    if knowledge_base is None:
        raise LookupError(f"知识库不存在：{kb_id}")
    return knowledge_base


async def delete_knowledge_base(
    db: AsyncSession,
    *,
    uid: str,
    kb_id: str,
) -> dict[str, Any]:
    """删除知识库及其文件、向量与图谱数据。"""
    knowledge_base = await KnowledgeBaseRepository(db).get_for_user(
        uid=uid,
        kb_id=kb_id,
    )
    if knowledge_base is None:
        raise LookupError(f"知识库不存在：{kb_id}")

    files = await KnowledgeFileRepository(db).list_for_user(
        uid=uid,
        kb_id=kb_id,
    )
    binding = await KnowledgeEmbeddingBindingRepository(db).get(
        uid=uid,
        kb_id=kb_id,
    )
    # 外部数据清理尽力而为，PostgreSQL 删除为准。
    knowledge = _get_knowledge("milvus")
    if binding is not None:
        for collection_name in (
            binding.collection_name,
            _entity_collection_name(uid, kb_id),
        ):
            try:
                await knowledge.drop_collection(
                    collection_name=collection_name
                )
            except Exception:
                logger.exception(
                    "知识库 Milvus 集合删除失败：%s", collection_name
                )
    try:
        await get_graph_store().delete_by_kb(kb_id=kb_id)
    except Exception:
        logger.exception("知识库 Neo4j 图谱删除失败：%s", kb_id)
    try:
        await get_storage().adelete_objects_by_prefix(
            _KNOWLEDGE_BUCKET,
            f"knowledge-files/{uid}/{kb_id}/",
        )
    except Exception:
        logger.exception("知识库 RustFS 对象删除失败：%s", kb_id)

    await db.delete(knowledge_base)
    await db.commit()
    return {"kb_id": kb_id, "deleted_file_count": len(files)}


async def list_files(
    db: AsyncSession,
    *,
    uid: str,
    kb_id: str,
) -> list[KnowledgeFile]:
    """列出当前用户指定知识库中的全部文件。"""
    knowledge_base = await KnowledgeBaseRepository(db).get_for_user(
        uid=uid,
        kb_id=kb_id,
    )
    if knowledge_base is None:
        raise LookupError(f"知识库不存在：{kb_id}")

    return await KnowledgeFileRepository(db).list_for_user(
        uid=uid,
        kb_id=kb_id,
    )


async def delete_file(
    db: AsyncSession,
    *,
    uid: str,
    kb_id: str,
    file_id: str,
) -> dict[str, Any]:
    """删除知识文件及其解析、索引与图谱数据。"""
    knowledge_files = KnowledgeFileRepository(db)
    file_record = await knowledge_files.get_for_user(
        uid=uid,
        kb_id=kb_id,
        file_id=file_id,
    )
    if file_record is None:
        raise LookupError(f"知识文件不存在：{file_id}")
    if file_record.status in {"parsing", "indexing", "extracting"}:
        raise ValueError(f"知识文件正在处理中，无法删除：{file_record.status}")

    knowledge = _get_knowledge("milvus")
    binding = await KnowledgeEmbeddingBindingRepository(db).get(
        uid=uid,
        kb_id=kb_id,
    )
    if binding is not None:
        for collection_name in (
            binding.collection_name,
            _entity_collection_name(uid, kb_id),
        ):
            await knowledge.delete(
                collection_name=collection_name,
                filter=f'file_id == "{file_id}"',
            )
    await get_graph_store().delete_by_file(kb_id=kb_id, file_id=file_id)
    await get_storage().adelete_objects_by_prefix(
        _KNOWLEDGE_BUCKET,
        f"knowledge-files/{uid}/{kb_id}/{file_id}/",
    )

    await db.delete(file_record)
    await db.commit()
    return {"file_id": file_id}


async def get_file_markdown(
    db: AsyncSession,
    *,
    uid: str,
    kb_id: str,
    file_id: str,
) -> dict[str, Any]:
    """读取知识文件已解析的 Markdown 产物。"""
    file_record = await KnowledgeFileRepository(db).get_for_user(
        uid=uid,
        kb_id=kb_id,
        file_id=file_id,
    )
    if file_record is None:
        raise LookupError(f"知识文件不存在：{file_id}")
    if not file_record.markdown_object_name:
        raise LookupError("解析结果不存在")

    markdown = await get_storage().adownload_file(
        _KNOWLEDGE_BUCKET,
        file_record.markdown_object_name,
    )
    return {
        "file_id": file_id,
        "markdown": markdown.decode(errors="ignore"),
    }


async def extract_file(
    db: AsyncSession,
    *,
    uid: str,
    kb_id: str,
    file_id: str,
) -> dict[str, Any]:
    """抽取知识文件实体关系并写入 Neo4j 与 Milvus 实体集合。"""
    knowledge_files = KnowledgeFileRepository(db)
    file_record = await knowledge_files.get_for_user(
        uid=uid,
        kb_id=kb_id,
        file_id=file_id,
    )
    if file_record is None:
        raise LookupError(f"知识文件不存在：{file_id}")
    if file_record.status not in {"indexed", "extracted"}:
        raise ValueError(
            f"知识文件当前状态不允许抽取：{file_record.status}"
        )
    if not file_record.markdown_object_name:
        raise ValueError("知识文件缺少已解析的 Markdown")
    re_extract = file_record.status == "extracted"

    await knowledge_files.update_status(
        file_record,
        status="extracting",
        error_message=None,
    )
    await db.commit()

    storage = get_storage()
    entity_store = _get_knowledge("milvus")
    graph_store = get_graph_store()
    entity_collection = _entity_collection_name(uid, kb_id)
    try:
        markdown = await storage.adownload_file(
            _KNOWLEDGE_BUCKET,
            file_record.markdown_object_name,
        )
        markdown_text = markdown.decode(errors="ignore")
        if len(markdown_text) > _EXTRACT_MAX_CHARS:
            logger.warning(
                "知识图谱抽取截断文档：%s 原始 %s 字符",
                file_id,
                len(markdown_text),
            )
            markdown_text = markdown_text[:_EXTRACT_MAX_CHARS]
        result = await GraphExtractor().extract(markdown_text)

        entities = []
        seen_names: set[str] = set()
        for entity in result.entities:
            key = entity.name.strip().casefold()
            if not key or key in seen_names:
                continue
            seen_names.add(key)
            entities.append(entity)

        if re_extract:
            await entity_store.delete(
                collection_name=entity_collection,
                filter=f'file_id == "{file_id}"',
            )
            await graph_store.delete_by_file(kb_id=kb_id, file_id=file_id)

        name_to_id: dict[str, str] = {}
        new_entities: list[dict[str, Any]] = []
        entity_rows: list[dict[str, Any]] = []
        binding = (
            await _require_binding(db, uid, kb_id) if entities else None
        )
        if binding is not None:
            embedding, _, _ = _create_embedding_service(
                binding.embedding_model_spec,
                expected_dimension=binding.embedding_dimension,
                batch_size=binding.embedding_batch_size,
            )
            vectors = await embedding.embed_texts(
                [entity.name for entity in entities]
            )
            for entity, vector in zip(entities, vectors, strict=True):
                name_key = entity.name.strip().casefold()
                hits = await entity_store.search_entities(
                    collection_name=entity_collection,
                    vector=vector,
                    limit=1,
                )
                if (
                    hits
                    and hits[0]["distance"] >= _ENTITY_DEDUPE_THRESHOLD
                ):
                    name_to_id[name_key] = hits[0]["id"]
                    continue
                entity_id = uuid4().hex
                name_to_id[name_key] = entity_id
                new_entities.append(
                    {
                        "entity_id": entity_id,
                        "name": entity.name,
                        "type": entity.type,
                        "description": entity.description,
                    }
                )
                entity_rows.append(
                    {
                        "id": entity_id,
                        "name": entity.name,
                        "entity_type": entity.type,
                        "description": entity.description,
                        "file_id": file_id,
                        "entity_embeding": vector,
                    }
                )
        if new_entities:
            await graph_store.upsert_entities(
                kb_id=kb_id,
                file_id=file_id,
                entities=new_entities,
            )
            await entity_store.upsert_entities(
                collection_name=entity_collection,
                dimension=binding.embedding_dimension,
                rows=entity_rows,
            )

        relations: list[dict[str, Any]] = []
        seen_relations: set[tuple[str, str, str]] = set()
        for relation in result.relations:
            source_id = name_to_id.get(relation.source.strip().casefold())
            target_id = name_to_id.get(relation.target.strip().casefold())
            if not source_id or not target_id or source_id == target_id:
                continue
            signature = (source_id, target_id, relation.type)
            if signature in seen_relations:
                continue
            seen_relations.add(signature)
            relations.append(
                {
                    "relation_id": uuid4().hex,
                    "source_entity_id": source_id,
                    "target_entity_id": target_id,
                    "type": relation.type,
                }
            )
        if relations:
            await graph_store.create_relations(
                kb_id=kb_id,
                file_id=file_id,
                relations=relations,
            )

        await knowledge_files.update_status(
            file_record,
            status="extracted",
            error_message=None,
        )
        await db.commit()
        return {
            "kb_id": kb_id,
            "file_id": file_id,
            "status": "extracted",
            "entity_count": len(entities),
            "relation_count": len(relations),
        }
    except Exception as exc:
        await db.rollback()
        file_record = await knowledge_files.get_for_user(
            uid=uid,
            kb_id=kb_id,
            file_id=file_id,
        )
        if file_record is not None:
            await knowledge_files.update_status(
                file_record,
                status="indexed",
                error_message=str(exc)[:2000],
            )
            await db.commit()
        raise


async def get_graph(
    db: AsyncSession,
    *,
    uid: str,
    kb_id: str,
) -> dict[str, Any]:
    """读取知识库全量实体与关系图谱。"""
    knowledge_base = await KnowledgeBaseRepository(db).get_for_user(
        uid=uid,
        kb_id=kb_id,
    )
    if knowledge_base is None:
        raise LookupError(f"知识库不存在：{kb_id}")

    graph = await get_graph_store().get_graph(kb_id=kb_id)
    return {
        "kb_id": kb_id,
        "nodes": graph["nodes"],
        "edges": graph["edges"],
        "entity_count": len(graph["nodes"]),
        "relation_count": len(graph["edges"]),
    }


async def search_entities(
    db: AsyncSession,
    *,
    uid: str,
    kb_id: str,
    query: str,
    limit: int,
) -> dict[str, Any]:
    """使用实体向量检索知识库实体。"""
    binding = await _require_binding(db, uid, kb_id)
    embedding, _, _ = _create_embedding_service(
        binding.embedding_model_spec,
        expected_dimension=binding.embedding_dimension,
        batch_size=binding.embedding_batch_size,
    )
    vector = await embedding.embed_query(query)
    hits = await _get_knowledge("milvus").search_entities(
        collection_name=_entity_collection_name(uid, kb_id),
        vector=vector,
        limit=limit,
    )
    return {
        "kb_id": kb_id,
        "hits": [
            {
                "entity_id": hit["id"],
                "name": hit["entity"]["name"],
                "type": hit["entity"]["entity_type"],
                "description": hit["entity"]["description"],
                "file_id": hit["entity"]["file_id"],
                "similarity": hit["distance"],
            }
            for hit in hits
        ],
    }


async def chat(
    db: AsyncSession,
    *,
    uid: str,
    kb_id: str,
    query: str,
    limit: int,
) -> dict[str, Any]:
    """基于知识库检索结果同步生成带引用的回答。"""
    result = await search(
        db,
        uid=uid,
        kb_id=kb_id,
        query=query,
        limit=limit,
    )
    hits = result["hits"]
    citations: list[dict[str, Any]] = []
    for hit in hits:
        entity = hit["entity"]
        metadata = dict(entity.get("metadata") or {})
        citations.append(
            {
                "file_id": entity["file_id"],
                "file_name": metadata.get("file_name") or entity["file_id"],
                "chunk_id": entity["chunk_id"],
                "excerpt": entity["chunk"][:_CITATION_EXCERPT_CHARS],
            }
        )
    if not citations:
        return {
            "kb_id": kb_id,
            "answer": _CHAT_NO_ANSWER,
            "citations": [],
        }

    segments = "\n\n".join(
        f"[{index}]（来源文件：{citation['file_name']}）\n"
        f"{hits[position]['entity']['chunk']}"
        for position, (citation, index) in enumerate(
            zip(citations, range(1, len(citations) + 1), strict=True)
        )
    )
    model = load_model(sys_config.default_model)
    response = await model.ainvoke(
        [
            SystemMessage(content=_CHAT_SYSTEM_PROMPT),
            HumanMessage(content=f"{segments}\n\n用户问题：{query}"),
        ]
    )
    return {
        "kb_id": kb_id,
        "answer": response.content,
        "citations": citations,
    }


def _get_knowledge(knowledge_type: str) -> MilvusKnowledge:
    """读取指定类型的向量存储。"""
    knowledge = KnowledgeFactory.create(knowledge_type)
    if not isinstance(knowledge, MilvusKnowledge):
        raise ValueError(f"暂不支持知识库类型：{knowledge_type}")
    return knowledge


async def _rerank_hits(
    *,
    query: str,
    hits: Sequence[Mapping[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    """重排 Milvus 命中并保留原始业务字段和向量分数。"""
    documents, hits_by_id = _prepare_rerank_documents(hits)
    results = await load_reranker().arerank(
        query,
        documents,
        top_n=limit,
    )

    reranked_hits: list[dict[str, Any]] = []
    for result in results:
        hit = dict(hits_by_id[result.document.id])
        hit["retrieval_rank"] = result.document.original_rank
        hit["rerank_score"] = result.relevance_score
        hit["rerank_rank"] = result.rerank_rank
        reranked_hits.append(hit)
    return reranked_hits


def _prepare_rerank_documents(
    hits: Sequence[Mapping[str, Any]],
) -> tuple[list[RerankDocument], dict[str, dict[str, Any]]]:
    """将 Milvus 命中转换为通用 Rerank 候选。"""
    documents: list[RerankDocument] = []
    hits_by_id: dict[str, dict[str, Any]] = {}

    for original_rank, raw_hit in enumerate(hits, start=1):
        hit = dict(raw_hit)
        raw_entity = hit.get("entity")
        entity = raw_entity if isinstance(raw_entity, Mapping) else hit

        document_id = str(
            entity.get("chunk_id") or hit.get("id") or ""
        ).strip()
        if not document_id:
            raise ValueError("Milvus 命中缺少 chunk_id")
        if document_id in hits_by_id:
            raise ValueError(f"Milvus 命中 chunk_id 重复：{document_id}")

        text = entity.get("chunk")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Milvus 命中缺少分块正文：{document_id}")

        raw_metadata = entity.get("metadata")
        metadata = (
            dict(raw_metadata) if isinstance(raw_metadata, Mapping) else {}
        )
        for key in ("file_id", "chunk_index"):
            value = entity.get(key)
            if value is not None:
                metadata.setdefault(key, value)

        documents.append(
            RerankDocument(
                id=document_id,
                text=text,
                original_rank=original_rank,
                retrieval_score=hit.get("distance"),
                metadata=metadata,
            )
        )
        hits_by_id[document_id] = hit

    return documents, hits_by_id


async def _require_binding(
    db: AsyncSession,
    uid: str,
    kb_id: str,
) -> KnowledgeEmbeddingBinding:
    """读取绑定，不允许查询路径隐式创建模型契约。"""
    binding = await KnowledgeEmbeddingBindingRepository(db).get(
        uid=uid,
        kb_id=kb_id,
    )
    if binding is None:
        raise LookupError(f"知识库尚未建立 Embedding 绑定：{kb_id}")
    return binding


def _create_embedding_service(
    model_spec: str | None,
    *,
    expected_dimension: int | None,
    batch_size: int | None,
) -> tuple[EmbeddingService, str, int]:
    """根据统一 Provider 配置装配无基础设施依赖的向量服务。"""
    resolved_spec, _, provider = resolve_embedding_model(model_spec)
    resolved_batch_size = batch_size or provider.batch_size
    service = EmbeddingService(
        load_embedding_model(resolved_spec),
        model_spec=resolved_spec,
        batch_size=resolved_batch_size,
        expected_dimension=expected_dimension,
    )
    return service, resolved_spec, resolved_batch_size


def _collection_name(uid: str, kb_id: str) -> str:
    """生成用户隔离且满足 Milvus 命名约束的集合名。"""
    digest = sha256(f"{uid}:{kb_id}".encode()).hexdigest()[:32]
    return f"kb_{digest}"


def _entity_collection_name(uid: str, kb_id: str) -> str:
    """生成实体向量集合名，与分块集合共用同一摘要。"""
    digest = sha256(f"{uid}:{kb_id}".encode()).hexdigest()[:32]
    return f"{_ENTITY_COLLECTION_PREFIX}{digest}"


def _binding_result(
    binding: KnowledgeEmbeddingBinding,
    **payload: Any,
) -> dict[str, Any]:
    """附带调用方可核对的持久模型契约。"""
    return {
        "kb_id": binding.kb_id,
        "embedding_model_spec": binding.embedding_model_spec,
        "embedding_dimension": binding.embedding_dimension,
        "embedding_batch_size": binding.embedding_batch_size,
        **payload,
    }
