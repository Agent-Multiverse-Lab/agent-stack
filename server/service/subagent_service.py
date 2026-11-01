import json
from dataclasses import fields
from datetime import datetime
from hashlib import sha256
from typing import TypedDict
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

import server.service.agent_run_service as agent_run_service
from server.service.input_message_service import AgentInputMsg
from server.service.model_service import resolve_runtime_model
from src.database.models import AgentRun, Conversation, Message
from src.database.repositories import AgentRepository, AgentRunRepository, ConversationRepository
from src.model import resolve_chat_model_selection


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
    created_by_run_id: str
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
    created_by_run_id: str
    agent_slug: str
    status: str
    terminal: bool
    error: str | None
    created_at: str | None
    started_at: str | None
    finished_at: str | None
    updated_at: str | None


SUBAGENT_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})
_RUNTIME_IDENTITY_FIELDS = frozenset(
    {"uid", "run_id", "thread_id", "request_id", "created_by_run_id", "parent_thread_id"}
)


def _datetime_text(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _serialize_subagent_run_status(run: AgentRun) -> SubAgentRunStatus:
    status = str(run.agent_status)
    return {
        "run_id": str(run.id),
        "thread_id": str(run.thread_id),
        "conversation_id": int(run.conversation_id),
        "created_by_run_id": str(run.created_by_run_id),
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
        "created_by_run_id": str(run.created_by_run_id),
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
        created_by_run_id: str,
        agent_slug: str,
        input_message: AgentInputMsg,
        uid: str,
        tool_call_id: str,
        request_id: str,
    ) -> SubAgentRunRecord:
        """落库并确认子会话、触发消息和运行记录，入队后立即返回。"""

        record = await self._persist_record(
            created_by_run_id=created_by_run_id,
            agent_slug=agent_slug,
            input_message=input_message,
            uid=uid,
            tool_call_id=tool_call_id,
            request_id=request_id,
        )
        await agent_run_service.enqueue_agent_run(record["run_id"])
        return record

    async def create_spawn_record(
        self,
        *,
        created_by_run_id: str,
        task: str,
        tools: list[str] | None = None,
        context: str = "",
        template: str | None = None,
        uid: str,
        tool_call_id: str,
        request_id: str,
    ) -> SubAgentRunRecord:
        """冻结本次任务配置，创建独立子 Run，并在提交后入队。"""
        from src.agents.buildin.subagents.subagent_context import SubAgentContext
        from src.agents.tool_catalog import resolve_spawn_tools

        if not task.strip():
            raise ValueError("子任务不能为空")
        child_request_id = sha256(
            f"{uid}:{created_by_run_id}:{tool_call_id}:{request_id}".encode()
        ).hexdigest()
        try:
            # 与父 Run 的取消、终态更新使用同一行锁，避免终态之后遗漏新子 Run。
            parent_run = await self.run_repository.get_by_id(created_by_run_id, for_update=True)
            if parent_run is None:
                raise ValueError(f"父运行不存在：{created_by_run_id}")
            if str(parent_run.uid) != uid:
                raise ValueError("父运行不属于当前用户")
            if parent_run.run_type not in {"chat", "resume"}:
                raise ValueError("子智能体不能继续委派子任务")
            parent_conversation = await self.conversation_repository.get_conversation_by_id(
                int(parent_run.conversation_id)
            )
            if parent_conversation is None or str(parent_conversation.uid) != uid:
                raise ValueError("父运行与父会话的用户归属不一致")

            existing_run = await self.run_repository.get_by_request_id(child_request_id)
            if existing_run is not None:
                record = await self._existing_spawn_record(existing_run, parent_run=parent_run)
            else:
                if parent_run.agent_status != "running":
                    raise ValueError("父运行已停止，不能创建子任务")
                repository = AgentRepository(self.db)
                executor = await repository.get_by_slug_for_run_type(
                    slug="generic_agent", run_type="subagent"
                )
                if executor is None:
                    raise ValueError("通用任务执行器不存在或已停用")
                selected = executor
                if template is not None:
                    selected = await repository.get_by_slug_for_run_type(slug=template, run_type="subagent")
                    if selected is None:
                        raise ValueError("子智能体模板不存在或已停用")
                if selected.backend_id != "SubAgentGraph":
                    raise ValueError("子智能体模板必须使用 SubAgentGraph")
                config = dict(selected.agent_config or {})
                if _RUNTIME_IDENTITY_FIELDS & config.keys():
                    raise ValueError("Agent 预设配置不能包含 Run 身份")
                if template is None:
                    config["tools"] = []
                    config["model"] = resolve_chat_model_selection(
                        model=(parent_run.run_metadata or {}).get("model"),
                        agent_model=config.get("model"),
                    )
                task_context = SubAgentContext(**config)
                task_context.model = resolve_chat_model_selection(agent_model=task_context.model)
                task_context.tools = await resolve_spawn_tools(task_context, tools)
                task_context.mcps = list(task_context.mcps)
                snapshot = {
                    item.name: getattr(task_context, item.name) for item in fields(task_context)
                    if item.name not in _RUNTIME_IDENTITY_FIELDS
                }
                json.dumps(snapshot, allow_nan=False)
                await resolve_runtime_model(self.db, task_context.model)
                record = await self._create_child_record(
                    created_by_run_id=created_by_run_id,
                    parent_conversation=parent_conversation,
                    agent_slug="generic_agent",
                    input_message=AgentInputMsg(
                        content=f"任务：\n{task}\n\n上下文：\n{context}" if context else task,
                        image_content=None,
                        msg_type="text",
                    ),
                    uid=uid,
                    child_request_id=child_request_id,
                    run_metadata={
                        "tool_call_id": tool_call_id,
                        "model": task_context.model,
                        "spawn": {"template": template, "agent_config": snapshot},
                    },
                )
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        if record["status"] == "pending":
            await agent_run_service.enqueue_agent_run(record["run_id"])
        return record

    async def _existing_spawn_record(
        self, run: AgentRun, *, parent_run: AgentRun
    ) -> SubAgentRunRecord:
        if (
            str(run.uid) != str(parent_run.uid)
            or str(run.created_by_run_id) != str(parent_run.id)
            or run.run_type != "subagent"
            or "spawn" not in (run.run_metadata or {})
        ):
            raise ValueError("request_id 已被其他请求使用")
        conversation = await self.conversation_repository.get_conversation_by_id(int(run.conversation_id))
        message = await self.db.get(Message, run.trigger_message_id)
        if conversation is None or message is None:
            raise ValueError("已有子任务的会话或输入消息不存在")
        return _build_record(conversation=conversation, message=message, run=run)

    async def get_parent_run(self, *, created_by_run_id: str) -> AgentRun:
        """按父 Agent context 中的 Run ID 查询父 Run。"""

        parent_run = await self.run_repository.get_by_id(created_by_run_id)

        if parent_run is None:
            raise ValueError(f"父 Agent Run 不存在：{created_by_run_id}")
        return parent_run

    async def get_child_run_status(
        self,
        *,
        created_by_run_id: str,
        run_id: str,
    ) -> SubAgentRunStatus:
        """校验父子 Run 归属并返回子 Agent Run 的数据库生命周期状态。"""

        run = await self.run_repository.get_child_for_parent(
            run_id=run_id,
            created_by_run_id=created_by_run_id,
        )

        if run is None:
            raise ValueError(f"子智能体运行不存在或不属于当前父运行：{run_id}")
        return _serialize_subagent_run_status(run)

    async def _persist_record(
        self,
        *,
        created_by_run_id: str,
        agent_slug: str,
        input_message: AgentInputMsg,
        uid: str,
        tool_call_id: str,
        request_id: str,
    ) -> SubAgentRunRecord:
        # TODO 需要再完善一下，因为目前来说，子 agent 落库的流程还没有梳理清楚， 2026-07-20

        try:
            parent_run = await self.run_repository.get_by_id(created_by_run_id)
            if parent_run is None:
                raise ValueError(f"父运行不存在：{created_by_run_id}")

            parent_conversation = (
                await self.conversation_repository.get_conversation_by_id(
                    int(parent_run.conversation_id)  # ty:ignore[invalid-argument-type]
                )
            )
            if parent_conversation is None:
                raise ValueError(f"父会话不存在：{parent_run.conversation_id}")
            if str(parent_conversation.uid) != str(parent_run.uid):
                raise ValueError("父运行与父会话的用户归属不一致")

            agent = await AgentRepository(self.db).get_by_slug_for_run_type(slug=agent_slug, run_type="subagent")
            if agent is None:
                raise ValueError("子智能体不存在或已停用")
            model = resolve_chat_model_selection(agent_model=(agent.agent_config or {}).get("model"))
            await resolve_runtime_model(self.db, model)

            record = await self._create_child_record(
                created_by_run_id=created_by_run_id,
                parent_conversation=parent_conversation,
                agent_slug=agent_slug,
                input_message=input_message,
                uid=uid,
                child_request_id=sha256(f"{uid}:{tool_call_id}:{request_id}".encode()).hexdigest(),
                run_metadata={"tool_call_id": tool_call_id, "model": model},
            )
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        return record

    async def _create_child_record(
        self,
        *,
        created_by_run_id: str,
        parent_conversation: Conversation,
        agent_slug: str,
        input_message: AgentInputMsg,
        uid: str,
        child_request_id: str,
        run_metadata: dict,
    ) -> SubAgentRunRecord:
        child_thread_id = str(uuid4())
        child_conversation = await self.conversation_repository.create_conversation(
            uid=uid,
            thread_id=child_thread_id,
            agent_slug=agent_slug,
            parent_conversation_id=int(parent_conversation.id),
            conversation_metadata={"model": run_metadata["model"]},
        )
        trigger_message = await self.conversation_repository.create_agent_input_message(
            conversation_id=int(child_conversation.id),
            content=input_message.content,
            image_content=input_message.image_content,
            message_type=input_message.msg_type,
        )
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
            created_by_run_id=created_by_run_id,
            run_metadata=run_metadata,
        )
        trigger_message.agent_run_id = child_run.id
        await self.db.flush()
        return _build_record(
            conversation=child_conversation,
            message=trigger_message,
            run=child_run,
        )
