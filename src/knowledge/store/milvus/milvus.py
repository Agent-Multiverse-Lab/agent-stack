from typing import Any

from pymilvus import (
    AsyncMilvusClient,
    CollectionSchema,
    DataType,
    FieldSchema,
    Function,
    FunctionType,
    MilvusClient,
)

from src.configs.config import config
from src.knowledge.base import BaseKnowledge, KnowledgeRecord


class MilvusKnowledge(BaseKnowledge):
    """提供知识分块的 Milvus 向量存取能力。"""

    name: str = "Milvus数据库"
    description: str = "知识库向量存储"

    def __init__(self, **kwargs: Any) -> None:
        self.milvus_uri = kwargs.get("milvus_uri") or config.milvus.uri
        self.milvus_token = kwargs.get("milvus_token") or config.milvus.token
        self.milvus_db = kwargs.get("milvus_db") or config.milvus.db_name
        self.milvus_collection: dict[str, str] = {}
        self.milvus_client: AsyncMilvusClient
        self._connect_initializer()

    async def build_file_index(
        self,
        *,
        collection_name: str,
        file_id: str,
        dimension: int,
        records: list[dict[str, Any] | KnowledgeRecord],
    ) -> dict[str, Any]:
        """将已向量化的文件分块批量写入 Milvus。"""
        if not collection_name:
            raise ValueError("Milvus Collection 名称不能为空")
        if not file_id:
            raise ValueError("文件 ID 不能为空")
        if dimension <= 0:
            raise ValueError("Embedding 维度必须为正整数")
        if not records:
            return {"upsert_count": 0}

        await self._get_milvus_collection(collection_name, dimension)
        rows = [
            self._normalize_record(record, position, file_id)
            for position, record in enumerate(records)
        ]
        result = await self.milvus_client.upsert(
            collection_name=collection_name,
            data=rows,
        )
        return {
            **result,
            "upsert_count": result.get("upsert_count", len(rows)),
        }

    async def search(
        self,
        *,
        collection_name: str,
        vector: list[float],
        limit: int,
    ) -> list[dict[str, Any]]:
        """使用稠密向量检索知识分块。"""
        if not await self.milvus_client.has_collection(
            collection_name=collection_name
        ):
            return []

        result = await self.milvus_client.search(
            collection_name=collection_name,
            data=[vector],
            anns_field="chunk_embeding",
            limit=limit,
            output_fields=[
                "chunk",
                "chunk_id",
                "chunk_index",
                "file_id",
                "metadata",
            ],
            search_params={
                "metric_type": "COSINE",
                "params": {},
            },
        )
        return result[0] if result else []

    async def delete(
        self,
        *,
        collection_name: str,
        ids: list[str] | None = None,
        record_ids: list[str] | None = None,
        filter: str | None = None,
    ) -> dict[str, Any]:
        """按主键或过滤条件删除知识分块。"""
        if not await self.milvus_client.has_collection(
            collection_name=collection_name
        ):
            return {"delete_count": 0}

        return await self.milvus_client.delete(
            collection_name=collection_name,
            ids=ids or record_ids,
            filter=filter,
        )

    async def status(self, *, collection_name: str) -> dict[str, Any]:
        """返回知识库 Collection 的存在状态和统计信息。"""
        exists = await self.milvus_client.has_collection(
            collection_name=collection_name
        )
        if not exists:
            return {
                "collection_name": collection_name,
                "exists": False,
            }

        stats = await self.milvus_client.get_collection_stats(
            collection_name=collection_name
        )
        return {
            "collection_name": collection_name,
            "exists": True,
            "stats": stats,
        }

    def _connect_initializer(self) -> None:
        """使用统一配置创建异步 Milvus 客户端。"""
        if not self.milvus_uri:
            raise ValueError("未配置 MILVUS_URI")

        self.milvus_client = AsyncMilvusClient(
            uri=self.milvus_uri,
            token=self.milvus_token or "",
            db_name=self.milvus_db or "",
        )

    async def _get_milvus_collection(
        self,
        collection_name: str,
        dimension: int,
    ) -> str:
        """获取 Collection，不存在时按实际向量维度创建。"""
        if collection_name in self.milvus_collection:
            return self.milvus_collection[collection_name]

        exists = await self.milvus_client.has_collection(
            collection_name=collection_name
        )
        if not exists:
            await self._create_collection(collection_name, dimension)

        self.milvus_collection[collection_name] = collection_name
        return collection_name

    async def _create_collection(
        self,
        collection_name: str,
        dimension: int,
    ) -> None:
        """创建支持稠密向量和 BM25 稀疏向量的 Collection。"""
        fields = [
            FieldSchema(
                name="id",
                dtype=DataType.VARCHAR,
                max_length=100,
                is_primary=True,
            ),
            FieldSchema(
                name="chunk",
                dtype=DataType.VARCHAR,
                max_length=65535,
                enable_analyzer=True,
                analyzer_params={"type": "chinese"},
                description="分块文本",
            ),
            FieldSchema(
                name="chunk_sparse",
                dtype=DataType.SPARSE_FLOAT_VECTOR,
                description="BM25 稀疏向量",
            ),
            FieldSchema(
                name="chunk_id",
                dtype=DataType.VARCHAR,
                max_length=100,
                description="分块业务 ID",
            ),
            FieldSchema(
                name="chunk_index",
                dtype=DataType.INT64,
                description="分块在文件内的顺序",
            ),
            FieldSchema(
                name="file_id",
                dtype=DataType.VARCHAR,
                max_length=100,
                description="分块所属文件",
            ),
            FieldSchema(
                name="metadata",
                dtype=DataType.JSON,
                description="分块元数据",
            ),
            FieldSchema(
                name="chunk_embeding",
                dtype=DataType.FLOAT_VECTOR,
                dimension=dimension,
                description="分块稠密向量",
            ),
        ]
        bm25_function = Function(
            name="chunk_bm25",
            input_field_names=["chunk"],
            output_field_names=["chunk_sparse"],
            function_type=FunctionType.BM25,
        )
        schema = CollectionSchema(
            fields=fields,
            functions=[bm25_function],
            description="知识库分块",
        )
        index_params = MilvusClient.prepare_index_params()
        index_params.add_index(
            field_name="chunk_embeding",
            index_name="chunk_embedding_index",
            index_type="AUTOINDEX",
            metric_type="COSINE",
        )
        index_params.add_index(
            field_name="chunk_sparse",
            index_name="chunk_sparse_index",
            index_type="SPARSE_INVERTED_INDEX",
            metric_type="BM25",
            params={"inverted_index_algo": "DAAT_MAXSCORE"},
        )

        await self.milvus_client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=index_params,
        )

    @classmethod
    def _normalize_record(
        cls,
        record: dict[str, Any] | KnowledgeRecord,
        position: int,
        file_id: str,
    ) -> dict[str, Any]:
        """将知识记录转换为 Milvus Schema 对应的数据行。"""
        record_id = str(cls._record_value(record, "id", "")).strip()
        content = cls._record_value(record, "content", "")
        vector = cls._record_value(record, "vector", None)
        metadata = dict(cls._record_value(record, "metadata", {}) or {})
        metadata["file_id"] = file_id
        if not record_id:
            raise ValueError("知识分块 ID 不能为空")
        if not isinstance(content, str) or not content.strip():
            raise ValueError(f"知识分块 {record_id} 的文本不能为空")
        if not isinstance(vector, list) or not vector:
            raise ValueError(f"知识分块 {record_id} 缺少向量")

        return {
            "id": record_id,
            "chunk": content,
            "chunk_id": str(metadata.get("chunk_id") or record_id),
            "chunk_index": int(metadata.get("chunk_index", position)),
            "file_id": file_id,
            "metadata": metadata,
            "chunk_embeding": vector,
        }

    @staticmethod
    def _record_value(
        record: dict[str, Any] | KnowledgeRecord,
        key: str,
        default: Any,
    ) -> Any:
        """兼容字典记录和 KnowledgeRecord 数据类。"""
        if isinstance(record, dict):
            return record.get(key, default)
        return getattr(record, key, default)
