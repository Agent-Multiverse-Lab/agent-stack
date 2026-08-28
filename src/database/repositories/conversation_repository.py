from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.database.models import AgentRun, Conversation, Message, ToolCall


class ConversationRepository:
    """读写 Conversation 及其持久化消息。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_top_level_for_user(
        self,
        *,
        uid: str,
        limit: int,
        query: str | None = None,
        before_activity_at: datetime | None = None,
        before_id: int | None = None,
    ) -> list[tuple[Conversation, datetime | None, datetime]]:
        """按最近活动时间倒序列出当前用户的顶层对话。"""
        if limit <= 0:
            raise ValueError("对话列表 limit 必须大于 0")
        if (before_activity_at is None) != (before_id is None):
            raise ValueError("对话列表游标字段不完整")

        message_activity = (
            select(
                Message.conversation_id,
                func.max(Message.created_at).label("last_message_at"),
            )
            .group_by(Message.conversation_id)
            .subquery()
        )
        last_activity_at = func.coalesce(
            message_activity.c.last_message_at,
            Conversation.updated_at,
        ).label("last_activity_at")
        statement = (
            select(
                Conversation,
                message_activity.c.last_message_at,
                last_activity_at,
            )
            .outerjoin(
                message_activity,
                message_activity.c.conversation_id == Conversation.id,
            )
            .where(
                Conversation.uid == uid,
                Conversation.parent_conversation_id.is_(None),
                Conversation.deleted_at.is_(None),
            )
        )

        if query is not None:
            pattern = f"%{query}%"
            statement = statement.where(
                or_(
                    Conversation.title.ilike(pattern),
                    Conversation.summary.ilike(pattern),
                )
            )
        if before_activity_at is not None and before_id is not None:
            statement = statement.where(
                or_(
                    last_activity_at < before_activity_at,
                    and_(
                        last_activity_at == before_activity_at,
                        Conversation.id < before_id,
                    ),
                )
            )

        result = await self.session.execute(
            statement.order_by(
                last_activity_at.desc(),
                Conversation.id.desc(),
            ).limit(limit)
        )
        return [
            (row[0], row[1], row[2])
            for row in result.all()
        ]

    async def get_top_level_for_user(
        self,
        *,
        uid: str,
        thread_id: str,
    ) -> Conversation | None:
        """按用户和 Thread ID 读取未删除的顶层对话。"""
        result = await self.session.execute(
            select(Conversation)
            .where(
                Conversation.uid == uid,
                Conversation.thread_id == thread_id,
                Conversation.parent_conversation_id.is_(None),
                Conversation.deleted_at.is_(None),
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_conversation_by_id(
        self,
        conversation_id: int | str,
    ) -> Conversation | None:
        """按内部 ID 读取未删除的对话。"""
        result = await self.session.execute(
            select(Conversation)
            .where(
                Conversation.id == int(conversation_id),
                Conversation.deleted_at.is_(None),
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_conversation_by_thread_id_for_user(
        self,
        thread_id: str,
        user_id: str,
    ) -> Conversation | None:
        """按用户和 Thread ID 读取任意层级的未删除对话。"""
        result = await self.session.execute(
            select(Conversation).where(
                Conversation.thread_id == thread_id,
                Conversation.uid == str(user_id),
                Conversation.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_last_message_at(
        self,
        *,
        conversation_id: int,
    ) -> datetime | None:
        """读取指定对话最后一条消息的创建时间。"""
        return await self.session.scalar(
            select(func.max(Message.created_at)).where(
                Message.conversation_id == conversation_id
            )
        )

    async def list_messages(
        self,
        *,
        conversation_id: int,
        limit: int,
        before_message_id: int | None = None,
    ) -> list[Message]:
        """按 ID 倒序读取指定对话的一页消息。"""
        statement = select(Message).where(
            Message.conversation_id == conversation_id
        )
        if before_message_id is not None:
            statement = statement.where(Message.id < before_message_id)

        result = await self.session.execute(
            statement.order_by(Message.id.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def list_tree_for_user(
        self,
        *,
        root_conversation_id: int,
        uid: str,
    ) -> list[Conversation]:
        """读取当前用户未删除的根对话及所有内部子对话。"""
        tree = (
            select(Conversation.id)
            .where(
                Conversation.id == root_conversation_id,
                Conversation.uid == uid,
                Conversation.deleted_at.is_(None),
            )
            .cte("conversation_tree", recursive=True)
        )
        child = aliased(Conversation)
        tree = tree.union_all(
            select(child.id).where(
                child.parent_conversation_id == tree.c.id,
                child.uid == uid,
                child.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(
            select(Conversation).join(
                tree,
                Conversation.id == tree.c.id,
            )
        )
        return list(result.scalars().all())

    async def create_conversation(
        self,
        uid: str,
        thread_id: str,
        agent_slug: str,
        parent_conversation_id: int | None = None,
        title: str | None = None,
        summary: str | None = None,
        conversation_metadata: dict | None = None,
    ) -> Conversation:
        """创建对话并刷新数据库生成字段。"""
        conversation = Conversation(
            uid=uid,
            thread_id=thread_id,
            agent_id=agent_slug,
            parent_conversation_id=parent_conversation_id,
            title=title or "",
            summary=summary,
            conversation_metadata=dict(conversation_metadata or {}),
        )
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def update_conversation(
        self,
        conversation: Conversation,
        *,
        title: str,
        summary: str | None,
        conversation_metadata: dict,
    ) -> Conversation:
        """更新允许修改的对话字段。"""
        conversation.title = title
        conversation.summary = summary
        conversation.conversation_metadata = dict(conversation_metadata)
        conversation.updated_at = datetime.now(UTC)
        await self.session.flush()
        return conversation

    async def soft_delete_tree(
        self,
        *,
        conversation_ids: Sequence[int],
        uid: str,
    ) -> None:
        """将当前用户的一组根子对话标记为已删除。"""
        if not conversation_ids:
            return

        deleted_at = datetime.now(UTC)
        await self.session.execute(
            update(Conversation)
            .where(
                Conversation.id.in_(conversation_ids),
                Conversation.uid == uid,
                Conversation.deleted_at.is_(None),
            )
            .values(
                deleted_at=deleted_at,
                updated_at=deleted_at,
            )
        )
        await self.session.flush()

    async def create_agent_input_message(
        self,
        *,
        conversation_id: int | str,
        content: str,
        image_content: str | None = None,
        message_type: str = "text",
        request_id: str | None = None,
        msg_metadata: dict | None = None,
    ) -> Message:
        """创建用户输入消息。"""
        return await self._create_message(
            conversation_id=conversation_id,
            role="user",
            content=content,
            image_content=image_content,
            message_type=message_type,
            request_id=request_id,
            msg_metadata=msg_metadata,
        )

    async def create_agent_output_message(
        self,
        *,
        conversation_id: int | str,
        agent_run_id: str,
        content: str,
    ) -> Message:
        """创建 Agent 输出消息。"""
        return await self._create_message(
            conversation_id=conversation_id,
            agent_run_id=agent_run_id,
            role="assistant",
            content=content,
        )

    async def add_message_by_thread_id(
        self,
        *,
        thread_id: str,
        user_id: str,
        agent_run_id: str,
        content: str,
        role: str,
        msg_metadata: dict | None = None,
    ) -> Message:
        """按用户和 Thread ID 添加 Agent 输出消息。"""
        conversation = await self.get_conversation_by_thread_id_for_user(
            thread_id=thread_id,
            user_id=user_id,
        )
        if conversation is None:
            raise LookupError("当前会话不存在或已删除")

        return await self._create_message(
            conversation_id=int(conversation.id),
            agent_run_id=agent_run_id,
            role=role,
            content=content,
            msg_metadata=msg_metadata,
        )

    # FIXEME: checkpoint 会返回完整历史，按 LangGraph Message ID 避免重复落库。
    async def get_message_by_langgraph_id(
        self,
        *,
        thread_id: str,
        user_id: str,
        langgraph_message_id: str,
    ) -> Message | None:
        result = await self.session.execute(
            select(Message)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Conversation.thread_id == thread_id,
                Conversation.uid == user_id,
                Conversation.deleted_at.is_(None),
                Message.msg_metadata["langgraph_message_id"].as_string()
                == langgraph_message_id,
            )
        )
        return result.scalar_one_or_none()

    async def add_tool_call(
        self,
        *,
        message_id: int,
        tool_call_id: str,
        tool_name: str,
        tool_arguments: dict,
        status: str
    ) -> ToolCall:
        """为 Assistant Message 创建工具调用。"""
        # FIXEME: Resume checkpoint 重读历史 AI Tool Call 时复用已有记录。
        if tool_call_id:
            result = await self.session.execute(
                select(ToolCall).where(ToolCall.tool_call_id == tool_call_id)
            )
            existing = result.scalar_one_or_none()
            if existing is not None:
                return existing

        tool_call = ToolCall(
            message_id=message_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            tool_arguments=dict(tool_arguments),
            status=status
        )
        self.session.add(tool_call)
        await self.session.flush()
        return tool_call

    async def update_tool_call(
        self,
        *,
        tool_call_id: str,
        tool_result: str,
        status: str,
    ) -> ToolCall:
        """按 LangGraph Tool Call ID 写入执行结果。"""
        result = await self.session.execute(
            select(ToolCall).where(ToolCall.tool_call_id == tool_call_id)
        )
        tool_call = result.scalar_one()
        tool_call.tool_result = tool_result
        tool_call.status = status
        await self.session.flush()
        return tool_call

    async def get_run_result_message(
        self,
        run_id: str,
    ) -> Message | None:
        """通过输出消息指针读取指定 Run 的结果。"""
        result = await self.session.execute(
            select(Message)
            .join(AgentRun, AgentRun.output_message_id == Message.id)
            .where(AgentRun.id == run_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def _create_message(
        self,
        *,
        conversation_id: int | str,
        role: str,
        content: str,
        agent_run_id: str | None = None,
        request_id: str | None = None,
        image_content: str | None = None,
        message_type: str = "text",
        status: str = "completed",
        msg_metadata: dict | None = None,
    ) -> Message:
        """创建一条持久化消息。"""
        message = Message(
            conversation_id=int(conversation_id),
            agent_run_id=agent_run_id,
            role=role,
            content=content,
            image_content=image_content,
            request_id=request_id,
            message_type=message_type,
            status=status,
            msg_metadata=dict(msg_metadata or {}),
        )
        self.session.add(message)
        await self.session.flush()
        return message
