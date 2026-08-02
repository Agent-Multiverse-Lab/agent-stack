from datetime import datetime
from hashlib import sha256
from typing import TypedDict
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

import server.service.agent_run_service as agent_run_service
from server.service.input_message_service import AgentInputMsg
from src.database.models import AgentRun, Conversation, Message
from src.database.repositories import AgentRunRepository, ConversationRepository


class SubAgentMessageRecord(TypedDict):
    id: int
    conversation_id: int
    agent_run_id: str
    role: str
    content: str
    status: str
    request_id: str | None


class SubAgentRunRecord(TypedDict):
    run_id: str
    thread_id: str
    conversation_id: int
    parent_conversation_id: int
    parent_run_id: str
    trigger_message_id: int
    request_id: str
    agent_slug: str
    status: str
    stream_url: str
    message: SubAgentMessageRecord


class SubAgentRunStatus(TypedDict):
    run_id: str
    thread_id: str
    conversation_id: int
    parent_run_id: str
    agent_slug: str
    status: str
    terminal: bool
    error: str | None
    created_at: str | None
    started_at: str | None
    finished_at: str | None
    updated_at: str | None


SUBAGENT_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})


def _datetime_text(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _serialize_subagent_run_status(run: AgentRun) -> SubAgentRunStatus:
    status = str(run.agent_status)
    return {
        "run_id": str(run.id),
        "thread_id": str(run.thread_id),
        "conversation_id": int(run.conversation_id),
        "parent_run_id": str(run.parent_run_id),
        "agent_slug": str(run.agent_id),
        "status": status,
        "terminal": status in SUBAGENT_TERMINAL_STATUSES,
        "error": str(run.error) if run.error is not None else None,
        "created_at": _datetime_text(run.created_at),
        "started_at": _datetime_text(run.started_at),
        "finished_at": _datetime_text(run.finished_at),
        "updated_at": _datetime_text(run.updated_at),
    }


def _build_record(
    *,
    conversation: Conversation,
    message: Message,
    run: AgentRun,
) -> SubAgentRunRecord:
    return {
        "run_id": str(run.id),
        "thread_id": str(conversation.thread_id),
        "conversation_id": int(conversation.id),
        "parent_conversation_id": int(conversation.parent_conversation_id),
        "parent_run_id": str(run.parent_run_id),
        "trigger_message_id": int(message.id),
        "request_id": str(run.request_id),
        "agent_slug": str(run.agent_id),
        "status": str(run.agent_status),
        "stream_url": (
            f"/api/agent/runs/{run.id}/events?thread_id={conversation.thread_id}"
        ),
        "message": {
            "id": int(message.id),
            "conversation_id": int(message.conversation_id),
            "agent_run_id": str(message.agent_run_id),
            "role": str(message.role),
            "content": str(message.content),
            "status": str(message.status),
            "request_id": (str(message.request_id) if message.request_id is not None else None),
        },
    }


class SubAgentRunService:
    """创建子智能体会话和触发消息，持久化 Run 后统一入队。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db: AsyncSession = db
        self.run_repository = AgentRunRepository(db)
        self.conversation_repository = ConversationRepository(db)

    async def create_subagent_record(
        self,
        *,
        parent_run_id: str,
        agent_slug: str,
        input_message: AgentInputMsg,
        uid: str,
        tool_call_id: str,
        request_id: str,
    ) -> SubAgentRunRecord:
        """落库并确认子会话、触发消息和运行记录，入队后立即返回。"""

        record = await self._persist_record(
            parent_run_id=parent_run_id,
            agent_slug=agent_slug,
            input_message=input_message,
            uid=uid,
            tool_call_id=tool_call_id,
            request_id=request_id,
        )
        await agent_run_service.enqueue_agent_run(record["run_id"])
        return record

    async def get_parent_run(self, *, parent_run_id: str) -> AgentRun:
        """按父 Agent context 中的 Run ID 查询父 Run。"""

        parent_run = await self.run_repository.get_by_id(parent_run_id)

        if parent_run is None:
            raise ValueError(f"父 Agent Run 不存在：{parent_run_id}")
        return parent_run

    async def get_child_run_status(
        self,
        *,
        parent_run_id: str,
        run_id: str,
    ) -> SubAgentRunStatus:
        """校验父子 Run 归属并返回子 Agent Run 的数据库生命周期状态。"""

        run = await self.run_repository.get_child_for_parent(
            run_id=run_id,
            parent_run_id=parent_run_id,
        )

        if run is None:
            raise ValueError(f"子智能体运行不存在或不属于当前父运行：{run_id}")
        return _serialize_subagent_run_status(run)

    async def _persist_record(
        self,
        *,
        parent_run_id: str,
        agent_slug: str,
        input_message: AgentInputMsg,
        uid: str,
        tool_call_id: str,
        request_id: str,
    ) -> SubAgentRunRecord:
        # TODO 需要再完善一下，因为目前来说，子 agent 落库的流程还没有梳理清楚， 2026-07-20

        try:
            parent_run = await self.run_repository.get_by_id(parent_run_id)
            if parent_run is None:
                raise ValueError(f"父运行不存在：{parent_run_id}")

            parent_conversation = (
                await self.conversation_repository.get_conversation_by_id(
                    int(parent_run.conversation_id)  # ty:ignore[invalid-argument-type]
                )
            )
            if parent_conversation is None:
                raise ValueError(f"父会话不存在：{parent_run.conversation_id}")
            if str(parent_conversation.uid) != str(parent_run.uid):
                raise ValueError("父运行与父会话的用户归属不一致")

            child_thread_id = str(uuid4())

            child_conversation = await self.conversation_repository.create_conversation(
                uid=uid,
                thread_id=child_thread_id,
                agent_slug=agent_slug,
                parent_conversation_id=int(parent_conversation.id),
            )
            trigger_message = (
                await self.conversation_repository.create_agent_input_message(
                    conversation_id=int(child_conversation.id),
                    content=input_message.content,
                    image_content=input_message.image_content,
                    message_type=input_message.msg_type,
                )
            )
            child_request_id = sha256(
                f"{uid}:{tool_call_id}:{request_id}".encode()
            ).hexdigest()
            trigger_message.request_id = child_request_id
            child_run = await self.run_repository.create_run(
                run_id=str(uuid4()),
                thread_id=child_thread_id,
                conversation_id=int(child_conversation.id),
                uid=uid,
                agent_slug=agent_slug,
                request_id=child_request_id,
                trigger_message_id=int(trigger_message.id),
                run_type="subagent",
                parent_run_id=parent_run_id,
            )
            trigger_message.agent_run_id = child_run.id
            await self.db.flush()
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        return _build_record(
            conversation=child_conversation,
            message=trigger_message,
            run=child_run,
        )
