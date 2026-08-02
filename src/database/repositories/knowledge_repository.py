from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import (
    Knowledge,
    KnowledgeBase,
    KnowledgeEmbeddingBinding,
    KnowledgeFile,
)


class KnowledgeBaseRepository:
    """读写用户知识库。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        kb_id: str,
        uid: str,
        name: str,
        description: str,
    ) -> KnowledgeBase:
        """创建知识库并刷新业务标识。"""
        knowledge_base = KnowledgeBase(
            kb_id=kb_id,
            uid=uid,
            name=name,
            description=description,
        )
        self.session.add(knowledge_base)
        await self.session.flush()
        return knowledge_base

    async def get_for_user(
        self,
        *,
        uid: str,
        kb_id: str,
    ) -> KnowledgeBase | None:
        """读取属于指定用户的知识库。"""
        result = await self.session.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.kb_id == kb_id,
                KnowledgeBase.uid == uid,
            )
        )
        return result.scalar_one_or_none()


class KnowledgeFileRepository:
    """读写知识库文件及解析状态。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        file_id: str,
        kb_id: str,
        original_file_name: str,
        original_object_name: str,
        content_type: str,
        file_size: int,
    ) -> KnowledgeFile:
        """创建已上传的知识文件记录。"""
        knowledge_file = KnowledgeFile(
            file_id=file_id,
            kb_id=kb_id,
            original_file_name=original_file_name,
            original_object_name=original_object_name,
            content_type=content_type,
            file_size=file_size,
            status="uploaded",
        )
        self.session.add(knowledge_file)
        await self.session.flush()
        return knowledge_file

    async def get_for_user(
        self,
        *,
        uid: str,
        kb_id: str,
        file_id: str,
    ) -> KnowledgeFile | None:
        """读取属于用户知识库的文件。"""
        result = await self.session.execute(
            select(KnowledgeFile)
            .join(
                KnowledgeBase,
                KnowledgeFile.kb_id == KnowledgeBase.kb_id,
            )
            .where(
                KnowledgeFile.file_id == file_id,
                KnowledgeFile.kb_id == kb_id,
                KnowledgeBase.uid == uid,
            )
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        knowledge_file: KnowledgeFile,
        *,
        status: str,
        markdown_object_name: str | None = None,
        error_message: str | None = None,
    ) -> KnowledgeFile:
        """更新文件状态及解析产物。"""
        knowledge_file.status = status
        knowledge_file.error_message = error_message
        if markdown_object_name is not None:
            knowledge_file.markdown_object_name = markdown_object_name
        await self.session.flush()
        return knowledge_file


class KnowledgeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_user(
        self,
        *,
        user_id: str,
        kind: str | None = None,
    ) -> list[Knowledge]:
        statement = select(Knowledge).where(Knowledge.user_id == int(user_id))
        if kind is not None:
            statement = statement.where(Knowledge.kind == kind)
        result = await self.session.execute(
            statement.order_by(
                Knowledge.updated_at.desc(),
                Knowledge.created_at.desc(),
            )
        )
        return list(result.scalars().all())


class KnowledgeEmbeddingBindingRepository:
    """读写知识库的 Embedding 持久绑定。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(
        self,
        *,
        uid: str,
        kb_id: str,
    ) -> KnowledgeEmbeddingBinding | None:
        """按用户和知识库标识读取绑定。"""
        return await self.session.get(
            KnowledgeEmbeddingBinding,
            (uid, kb_id),
        )

    async def create(
        self,
        *,
        uid: str,
        kb_id: str,
        collection_name: str,
        embedding_model_spec: str,
        embedding_dimension: int,
        embedding_batch_size: int,
    ) -> KnowledgeEmbeddingBinding:
        """创建并刷新知识库的首次模型绑定。"""
        binding = KnowledgeEmbeddingBinding(
            uid=uid,
            kb_id=kb_id,
            collection_name=collection_name,
            embedding_model_spec=embedding_model_spec,
            embedding_dimension=embedding_dimension,
            embedding_batch_size=embedding_batch_size,
        )
        self.session.add(binding)
        await self.session.flush()
        return binding
