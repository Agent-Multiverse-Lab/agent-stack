from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from src.database.models import (
    AUDIT_MESSAGE_TYPES,
    AgentRun,
    Conversation,
    Message,
    SubAgentConversationRelation,
    ToolCall,
)


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
        before_pinned_at: datetime | None = None,
        project_id: str | None = None,
        unassigned: bool = False,
        pinned: bool | None = None,
    ) -> list[tuple[Conversation, datetime]]:
        """按最近活动时间倒序列出当前用户的顶层对话。"""
        if limit <= 0:
            raise ValueError("对话列表 limit 必须大于 0")
        if (before_activity_at is None) != (before_id is None):
            raise ValueError("对话列表游标字段不完整")

        message_activity = (
            select(
                Message.conversation_id,
                func.max(Message.created_at).label("last_activity_at"),
            )
            .group_by(Message.conversation_id)
            .subquery()
        )
        last_activity_at = func.coalesce(
            message_activity.c.last_activity_at,
            Conversation.updated_at,
        ).label("last_activity_at")
        statement = (
            select(
                Conversation,
                last_activity_at,
            )
            .outerjoin(
                message_activity,
                message_activity.c.conversation_id == Conversation.id,
            )
            .where(
                Conversation.uid == uid,
                ~exists(
                    select(SubAgentConversationRelation.id).where(
                        SubAgentConversationRelation.child_conversation_id
                        == Conversation.id,
                        SubAgentConversationRelation.uid == uid,
                        SubAgentConversationRelation.deleted_at.is_(None),
                    )
                ),
                Conversation.deleted_at.is_(None),
            )
        )

        if project_id is not None:
            statement = statement.where(Conversation.project_id == project_id)
        if unassigned:
            statement = statement.where(Conversation.project_id.is_(None))
        if pinned is not None:
            statement = statement.where(
                Conversation.pinned_at.is_not(None) if pinned else Conversation.pinned_at.is_(None)
            )
        if query is not None:
            pattern = f"%{query}%"
            statement = statement.where(or_(
                Conversation.title.ilike(pattern),
                Conversation.summary.ilike(pattern),
            ))
        if before_activity_at is not None and before_id is not None:
            activity_after = or_(
                last_activity_at < before_activity_at,
                and_(last_activity_at == before_activity_at, Conversation.id < before_id),
            )
            if before_pinned_at is None:
                statement = statement.where(Conversation.pinned_at.is_(None), activity_after)
            else:
                statement = statement.where(or_(
                    Conversation.pinned_at.is_(None),
                    Conversation.pinned_at < before_pinned_at,
                    and_(Conversation.pinned_at == before_pinned_at, activity_after),
                ))

        result = await self.session.execute(
            statement.order_by(
                Conversation.pinned_at.desc().nulls_last(),
                last_activity_at.desc(),
                Conversation.id.desc(),
            ).limit(limit)
        )
        return [
            (row[0], row[1])
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
                ~exists(
                    select(SubAgentConversationRelation.id).where(
                        SubAgentConversationRelation.child_conversation_id
                        == Conversation.id,
                        SubAgentConversationRelation.uid == uid,
                        SubAgentConversationRelation.deleted_at.is_(None),
                    )
                ),
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
        *,
        for_update: bool = False,
    ) -> Conversation | None:
        """按用户和 Thread ID 读取任意层级的未删除对话。"""
        statement = select(Conversation).where(
            Conversation.thread_id == thread_id,
            Conversation.uid == str(user_id),
            Conversation.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_messages(
        self,
        *,
        conversation_id: int,
        limit: int,
        before_message_id: int | None = None,
    ) -> list[Message]:
        """按 ID 倒序读取指定对话的一页消息。"""
        statement = select(Message).where(
            Message.conversation_id == conversation_id,
            # 已结束的审计操作也是执行过程；running 行仍由 SSE 恢复。
            or_(
                func.coalesce(Message.message_type, "text").not_in(AUDIT_MESSAGE_TYPES),
                Message.execution_status != "running",
            ),
        )
        if before_message_id is not None:
            statement = statement.where(Message.id < before_message_id)

        result = await self.session.execute(
            statement.options(selectinload(Message.tool_calls))
            .order_by(Message.id.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def list_tool_audit_ids(self, *, conversation_id: int) -> set[str]:
        """用于去重 checkpoint ToolCall 与生命周期审计的同一次调用。"""
        result = await self.session.execute(select(Message.operation_id).where(
            Message.conversation_id == conversation_id,
            Message.message_type == "tool_audit",
        ))
        return set(result.scalars().all())

    async def save_agent_state(self, *, run: AgentRun, state: dict) -> Message | None:
        """每个 Run 保留一条最新任务状态，空列表也会覆盖已有状态。"""
        result = await self.session.execute(select(Message).where(
            Message.agent_run_id == run.id,
            Message.message_type == "agent_state",
        ))
        message = result.scalar_one_or_none()
        if message is not None:
            message.msg_metadata = {"agent_state": state}
            await self.session.flush()
            return message
        if not state.get("agent_todo"):
            return None
        return await self._create_message(
            conversation_id=run.conversation_id,
            agent_run_id=run.id,
            role="ai",
            content="",
            message_type="agent_state",
            msg_metadata={"agent_state": state},
        )

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
        relation = aliased(SubAgentConversationRelation)
        tree = tree.union_all(
            select(child.id)
            .join(
                relation,
                relation.child_conversation_id == child.id,
            )
            .where(
                relation.parent_conversation_id == tree.c.id,
                relation.uid == uid,
                relation.deleted_at.is_(None),
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
        title: str | None = None,
        summary: str | None = None,
        conversation_metadata: dict | None = None,
        project_id: str | None = None,
    ) -> Conversation:
        """创建对话并刷新数据库生成字段。"""
        conversation = Conversation(
            uid=uid,
            thread_id=thread_id,
            agent_id=agent_slug,
            title=title or "",
            summary=summary,
            conversation_metadata=dict(conversation_metadata or {}),
            project_id=project_id,
        )
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def create_subagent_relation(
        self,
        *,
        uid: str,
        parent_conversation: Conversation,
        child_conversation: Conversation,
        created_by_run_id: str,
    ) -> SubAgentConversationRelation:
        """创建父子 Agent 会话关系，并验证双方属于同一用户。"""
        normalized_uid = str(uid)
        if str(parent_conversation.uid) != normalized_uid:
            raise ValueError("父会话不属于当前用户")
        if str(child_conversation.uid) != normalized_uid:
            raise ValueError("子会话不属于当前用户")
        if int(parent_conversation.id) == int(child_conversation.id):
            raise ValueError("父子会话不能相同")

        relation = SubAgentConversationRelation(
            uid=normalized_uid,
            parent_conversation_id=int(parent_conversation.id),
            child_conversation_id=int(child_conversation.id),
            created_by_run_id=created_by_run_id,
        )
        self.session.add(relation)
        await self.session.flush()
        return relation

    async def update_conversation(
        self,
        conversation: Conversation,
        *,
        title: str,
        summary: str | None,
        conversation_metadata: dict,
        organization: dict | None = None,
    ) -> Conversation:
        """更新允许修改的对话字段。"""
        conversation.title = title
        conversation.summary = summary
        conversation.conversation_metadata = dict(conversation_metadata)
        if organization is not None:
            if "project_id" in organization:
                conversation.project_id = organization["project_id"]
            if "pinned" in organization:
                conversation.pinned_at = datetime.now(UTC) if organization["pinned"] else None
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
        await self.session.execute(
            update(SubAgentConversationRelation)
            .where(
                SubAgentConversationRelation.uid == uid,
                SubAgentConversationRelation.deleted_at.is_(None),
                or_(
                    SubAgentConversationRelation.parent_conversation_id.in_(conversation_ids),
                    SubAgentConversationRelation.child_conversation_id.in_(conversation_ids),
                ),
            )
            .values(deleted_at=deleted_at)
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

    async def bind_input_message_to_run(self, run: AgentRun) -> None:
        """在 Run 创建事务内关联已接收的输入消息。"""
        await self.session.execute(
            update(Message)
            .where(
                Message.id == run.trigger_message_id,
                Message.conversation_id == run.conversation_id,
            )
            .values(agent_run_id=run.id)
        )
        await self.session.flush()

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
        content: str,
        role: str,
        agent_run_id: str | None = None,
        request_id: str | None = None,
        image_content: str | None = None,
        message_type: str = "text",
        status: str = "completed",
        commit: bool = False,
        msg_metadata: dict | None = None,
    ) -> Message:
        """按用户和 Thread ID 添加消息，透传全部可写业务字段。"""
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
            request_id=request_id,
            image_content=image_content,
            message_type=message_type,
            status=status,
            started_at=datetime.now(UTC),
            execution_status="completed",
            commit=commit,
            msg_metadata=msg_metadata,
        )

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
        sequence: int | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        execution_status: str | None = "completed",
        operation_id: str | None = None,
        usage: dict | None = None,
        commit: bool = False,
        msg_metadata: dict | None = None,
    ) -> Message:
        """创建一条持久化消息：未指定序号时分配会话内稳定序号并记录开始时间。"""
        if sequence is None:
            sequence = await self.next_sequence(conversation_id)
        now = datetime.now(UTC)
        message = Message(
            conversation_id=int(conversation_id),
            agent_run_id=agent_run_id,
            role=role,
            content=content,
            image_content=image_content,
            request_id=request_id,
            message_type=message_type,
            status=status,
            sequence=sequence,
            started_at=started_at or now,
            finished_at=finished_at,
            execution_status=execution_status,
            operation_id=operation_id,
            usage=usage,
            msg_metadata=dict(msg_metadata or {}),
        )
        self.session.add(message)
        await self.session.flush()
        if commit:
            await self.session.commit()
        return message

    async def next_sequence(self, conversation_id: int | str) -> int:
        """返回指定会话的下一个展示序号。

        审计行使用 ProtocolEvent 的 seq（Run 内顺序），不参与会话级序号分配，
        避免流式事件序号污染普通消息的展示顺序。
        """
        result = await self.session.execute(
            select(func.max(Message.sequence)).where(
                Message.conversation_id == int(conversation_id),
                func.coalesce(Message.message_type, "text").not_in(
                    AUDIT_MESSAGE_TYPES
                ),
            )
        )
        return int(result.scalar() or 0) + 1
