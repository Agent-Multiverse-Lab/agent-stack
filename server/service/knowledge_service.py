"""知识库向量化与存储用例。"""

from collections.abc import Sequence
from hashlib import sha256
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

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
from src.knowledge.store.milvus.milvus import MilvusKnowledge
from src.model import (
    load_embedding_model,
    resolve_embedding_model,
)
from src.storage import MinioStorage, get_storage, sanitize_filename

_KNOWLEDGE_BUCKET = "knowledgebases"


class EmbeddingModelConflictError(ValueError):
    """请求模型与知识库持久绑定冲突。"""


class KnowledgeService:
    """协调知识库模型绑定、向量化和 Milvus 操作。"""

    def __init__(
        self,
        db: AsyncSession,
        knowledge_type: str = "milvus",
        *,
        storage: MinioStorage | None = None,
        pipeline: Pipeline | None = None,
    ) -> None:
        self.db = db
        self.knowledge_type = knowledge_type
        self._knowledge: MilvusKnowledge | None = None
        self.storage = storage or get_storage()
        self.pipeline = pipeline or Pipeline()
        self.knowledge_bases = KnowledgeBaseRepository(db)
        self.knowledge_files = KnowledgeFileRepository(db)
        self.bindings = KnowledgeEmbeddingBindingRepository(db)

    async def create_knowledge_base(
        self,
        *,
        uid: str,
        name: str,
        description: str = "",
    ) -> KnowledgeBase:
        """创建用户知识库。"""
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("知识库名称不能为空")

        knowledge_base = await self.knowledge_bases.create(
            kb_id=uuid4().hex,
            uid=uid,
            name=normalized_name,
            description=description.strip(),
        )
        await self.db.commit()
        return knowledge_base

    async def upload_file(
        self,
        *,
        uid: str,
        kb_id: str,
        file_name: str,
        content: bytes,
        content_type: str | None = None,
    ) -> KnowledgeFile:
        """上传知识库原文件并创建独立文件记录。"""
        knowledge_base = await self.knowledge_bases.get_for_user(
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

        await self.storage.aupload_file(
            _KNOWLEDGE_BUCKET,
            original_object_name,
            content,
            content_type or "application/octet-stream",
        )
        try:
            knowledge_file = await self.knowledge_files.create(
                file_id=file_id,
                kb_id=kb_id,
                original_file_name=file_name,
                original_object_name=original_object_name,
                content_type=content_type or "application/octet-stream",
                file_size=len(content),
            )
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            await self.storage.adelete_file(
                _KNOWLEDGE_BUCKET,
                original_object_name,
            )
            raise
        return knowledge_file

    async def parse_file(
        self,
        *,
        uid: str,
        kb_id: str,
        file_id: str,
    ) -> KnowledgeFile:
        """解析知识文件并将 Markdown 保存到 MinIO。"""
        knowledge_file = await self.knowledge_files.get_for_user(
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

        await self.knowledge_files.update_status(
            knowledge_file,
            status="parsing",
        )
        await self.db.commit()

        markdown_object_name = (
            f"knowledge-files/{uid}/{kb_id}/{file_id}/parsed/document.md"
        )
        try:
            content = await self.storage.adownload_file(
                _KNOWLEDGE_BUCKET,
                knowledge_file.original_object_name,
            )
            document = await self.pipeline.parse_document(
                content,
                file_name=knowledge_file.original_file_name,
            )
            if not document.markdown.strip():
                raise ValueError("Parser 未生成有效 Markdown")

            await self.storage.aupload_file(
                _KNOWLEDGE_BUCKET,
                markdown_object_name,
                document.markdown.encode("utf-8"),
                "text/markdown",
            )
            await self.knowledge_files.update_status(
                knowledge_file,
                status="parsed",
                markdown_object_name=markdown_object_name,
            )
            await self.db.commit()
            return knowledge_file
        except Exception as exc:
            await self.db.rollback()
            knowledge_file = await self.knowledge_files.get_for_user(
                uid=uid,
                kb_id=kb_id,
                file_id=file_id,
            )
            if knowledge_file is not None:
                await self.knowledge_files.update_status(
                    knowledge_file,
                    status="failed",
                    error_message=str(exc)[:2000],
                )
                await self.db.commit()
            raise

    async def index_file(
        self,
        *,
        uid: str,
        kb_id: str,
        file_id: str,
    ) -> dict[str, Any]:
        """将用户确认后的 Markdown 分块、向量化并写入 Milvus。"""
        file_record = await self.knowledge_files.get_for_user(
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

        await self.knowledge_files.update_status(
            file_record,
            status="indexing",
            error_message=None,
        )
        await self.db.commit()

        try:
            markdown = await self.storage.adownload_file(
                _KNOWLEDGE_BUCKET,
                file_record.markdown_object_name,
            )
            document = await self.pipeline.parse_document(
                markdown,
                file_name="document.md",
            )
            chunks = self.pipeline.chunk_document(document)
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

            binding = await self.bindings.get(uid=uid, kb_id=kb_id)
            binding_created = binding is None
            embedding, resolved_spec, batch_size = (
                self._create_embedding_service(
                    (
                        binding.embedding_model_spec
                        if binding is not None
                        else None
                    ),
                    expected_dimension=(
                        binding.embedding_dimension
                        if binding is not None
                        else None
                    ),
                    batch_size=(
                        binding.embedding_batch_size
                        if binding is not None
                        else None
                    ),
                )
            )
            contents = [record["content"].strip() for record in records]
            vectors = await embedding.embed_texts(contents)
            dimension = embedding.dimension
            if dimension is None:
                raise RuntimeError("Embedding 模型未返回向量维度")

            if binding is None:
                binding = await self.bindings.create(
                    uid=uid,
                    kb_id=kb_id,
                    collection_name=self._collection_name(uid, kb_id),
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
            await self._get_knowledge().build_file_index(
                collection_name=binding.collection_name,
                file_id=file_id,
                dimension=binding.embedding_dimension,
                records=knowledge_records,
            )
            if binding_created:
                await self.db.commit()

            await self.knowledge_files.update_status(
                file_record,
                status="indexed",
                error_message=None,
            )
            await self.db.commit()
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
            await self.db.rollback()
            file_record = await self.knowledge_files.get_for_user(
                uid=uid,
                kb_id=kb_id,
                file_id=file_id,
            )
            if file_record is not None:
                await self.knowledge_files.update_status(
                    file_record,
                    status="parsed",
                    error_message=str(exc),
                )
                await self.db.commit()
            raise

    async def search(
        self,
        *,
        uid: str,
        kb_id: str,
        query: str,
        limit: int,
    ) -> dict[str, Any]:
        """始终使用知识库绑定模型生成查询向量。"""
        binding = await self._require_binding(uid, kb_id)
        embedding, _, _ = self._create_embedding_service(
            binding.embedding_model_spec,
            expected_dimension=binding.embedding_dimension,
            batch_size=binding.embedding_batch_size,
        )
        vector = await embedding.embed_query(query)
        hits = await self._get_knowledge().search(
            collection_name=binding.collection_name,
            vector=vector,
            limit=limit,
        )
        return self._binding_result(binding, hits=hits)

    async def delete_records(
        self,
        *,
        uid: str,
        kb_id: str,
        record_ids: Sequence[str],
    ) -> dict[str, Any]:
        """删除用户知识库中的指定向量记录。"""
        if not record_ids:
            raise ValueError("待删除记录 ID 不能为空")

        binding = await self._require_binding(uid, kb_id)
        result = await self._get_knowledge().delete(
            collection_name=binding.collection_name,
            record_ids=record_ids,
        )
        return self._binding_result(binding, result=result)

    async def status(self, *, uid: str, kb_id: str) -> dict[str, Any]:
        """读取绑定知识库对应 Milvus 集合的状态。"""
        binding = await self._require_binding(uid, kb_id)
        result = await self._get_knowledge().status(
            collection_name=binding.collection_name
        )
        return self._binding_result(binding, status=result)

    def _get_knowledge(self) -> MilvusKnowledge:
        """按需创建向量存储，解析阶段不触发 Milvus。"""
        if self._knowledge is None:
            knowledge = KnowledgeFactory.create(self.knowledge_type)
            if not isinstance(knowledge, MilvusKnowledge):
                raise ValueError(
                    f"暂不支持知识库类型：{self.knowledge_type}"
                )
            self._knowledge = knowledge
        return self._knowledge

    async def _require_binding(
        self,
        uid: str,
        kb_id: str,
    ) -> KnowledgeEmbeddingBinding:
        """读取绑定，不允许查询路径隐式创建模型契约。"""
        binding = await self.bindings.get(uid=uid, kb_id=kb_id)
        if binding is None:
            raise LookupError(f"知识库尚未建立 Embedding 绑定：{kb_id}")
        return binding

    @staticmethod
    def _check_requested_model(
        binding: KnowledgeEmbeddingBinding,
        requested_model: str | None,
    ) -> None:
        """拒绝已绑定知识库切换向量模型。"""
        if requested_model is None:
            return

        requested_spec, _, _ = resolve_embedding_model(requested_model)
        if requested_spec != binding.embedding_model_spec:
            raise EmbeddingModelConflictError(
                "知识库已绑定 Embedding 模型 "
                f"{binding.embedding_model_spec}，不能切换为 {requested_spec}"
            )

    @staticmethod
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

    @staticmethod
    def _collection_name(uid: str, kb_id: str) -> str:
        """生成用户隔离且满足 Milvus 命名约束的集合名。"""
        digest = sha256(f"{uid}:{kb_id}".encode("utf-8")).hexdigest()[:32]
        return f"kb_{digest}"

    @staticmethod
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
