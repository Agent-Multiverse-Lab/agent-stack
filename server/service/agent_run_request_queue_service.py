from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.exception import AgentRunConflictError
from server.service.arq_queue_servcie import enqueue_agent_run
from src.database.models import AgentRun, AgentRunRequest, Conversation, User
from src.database.repositories import (
    AgentRunRepository,
    AgentRunRequestQueueRepository,
    AgentRunRequestRepository,
    ConversationRepository,
)
from src.database.session import session_context
from src.model.runtime import validate_model
from src.utils import logger


@dataclass(frozen=True)
class AgentRunRequestInput:
    """Run 创建业务接收的已保存请求及当前会话配置。"""

    request_id: str
    uid: str
    thread_id: str
    agent_id: str
    trigger_message_id: int
    conversation_metadata: dict[str, Any]


def build_queued_response(
    request: AgentRunRequest,
    active_run: AgentRun | None = None,
    *,
    queue_position: int = 1,
) -> dict[str, Any]:
    """构造等待区 202 排队响应载荷。"""
    return {
        "run_id": None,
        "thread_id": request.thread_id,
        "status": "queued",
        "dispatch_policy": request.dispatch_policy,
        "request_id": request.request_id,
        "queue_position": queue_position,
        "steering_run_id": (
            str(active_run.id)
            if active_run is not None and request.dispatch_policy == "steer"
            else None
        ),
        "stream_url": None,
    }


async def enqueue_committed_run(
    db: AsyncSession,
    run: AgentRun,
    *,
    enqueue_fn: Callable[[str], Awaitable[None]] | None = None,
) -> AgentRun:
    """在事务提交后投递 AgentRun 到 ARQ，入队失败时标记未认领 Run 为 failed。"""
    enqueue = enqueue_fn or enqueue_agent_run
    try:
        await enqueue(str(run.id))
    except Exception as exc:
        logger.exception("Agent Run 入队失败：run_id=%s", run.id)
        failed_run, _ = await AgentRunRepository(db).set_agent_terminal(
            str(run.id),
            status="failed",
            error=f"Agent Run 入队失败：{exc}",
            error_type=type(exc).__name__,
        )
        await db.commit()
        return failed_run or run
    return run


async def convert_request_to_run(
    db: AsyncSession,
    request: AgentRunRequest,
    conversation: Conversation,
    *,
    resolve_model_fn: Callable[..., Awaitable[Any]] | None = None,
) -> AgentRun:
    """校验当前会话模型并将 AgentRunRequest 转换为待执行 AgentRun。"""
    dispatch = AgentRunRequestInput(
        request_id=request.request_id,
        uid=request.uid,
        thread_id=request.thread_id,
        agent_id=request.agent_id,
        trigger_message_id=request.trigger_message_id,
        conversation_metadata=dict(conversation.conversation_metadata or {}),
    )
    metadata = {**dispatch.conversation_metadata, "request_id": dispatch.request_id}
    resolver = resolve_model_fn or validate_model
    await resolver(db, metadata.get("model"))
    return await AgentRunRequestQueueRepository(db).convert_request_to_run(
        request=request,
        conversation=conversation,
        run_metadata=metadata,
    )


async def dispatch_next_queued_request(thread_id: str) -> AgentRun | None:
    """在会话行锁下出队优先级最高的排队请求，转换为 AgentRun 并投入 ARQ。"""
    async with session_context() as db:
        conversation = await db.scalar(
            select(Conversation)
            .where(
                Conversation.thread_id == thread_id,
                Conversation.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if conversation is None:
            return None
        runs = AgentRunRepository(db)
        if (
            await runs.get_latest_active_for_thread(
                uid=conversation.uid, thread_id=thread_id
            )
            is not None
            or await runs.get_pending_interaction_run(
                uid=conversation.uid, thread_id=thread_id
            )
            is not None
        ):
            return None
        request = await AgentRunRequestQueueRepository(db).pop_next_queued_for_thread(
            thread_id
        )
        if request is None:
            return None
        run = await convert_request_to_run(db, request, conversation)
        await db.commit()
        return await enqueue_committed_run(db, run)


async def _require_owned_request_with_thread_lock(
    *,
    db: AsyncSession,
    uid: str,
    request_id: str,
) -> tuple[
    AgentRunRequestQueueRepository,
    AgentRunRepository,
    Conversation,
    AgentRunRequest,
]:
    """校验等待区请求归属后持 Conversation FOR UPDATE 行锁复查最新状态。"""
    agent_run_request_repo = AgentRunRequestRepository(db)
    queue_repo = AgentRunRequestQueueRepository(db)
    conversation_repo = ConversationRepository(db)
    run_repo = AgentRunRepository(db)
    initial = await agent_run_request_repo.get_run_request_by_request_id(request_id)
    if initial is None or str(initial.uid) != uid:
        raise LookupError("等待区请求不存在")
    conversation = await conversation_repo.get_conversation_by_thread_id_for_user(
        thread_id=str(initial.thread_id),
        user_id=uid,
        for_update=True,
    )
    if conversation is None:
        raise LookupError("当前会话不存在或已删除")
    request = await agent_run_request_repo.get_run_request_by_request_id(request_id)
    if request is None or str(request.uid) != uid:
        raise LookupError("等待区请求不存在")
    return queue_repo, run_repo, conversation, request


async def _raise_dispatched_conflict(
    run_repo: AgentRunRepository, request_id: str
) -> None:
    existing_run = await run_repo.get_run_by_request_id(request_id)
    raise AgentRunConflictError(
        "请求已开始执行",
        run_id=str(existing_run.id) if existing_run is not None else None,
    )


async def cancel_queued_request(
    *,
    db: AsyncSession,
    current_user: User,
    request_id: str,
) -> dict[str, str]:
    """在会话行锁下逻辑软取消等待区请求及其未绑定输入消息。"""
    uid = str(current_user.uid)
    try:
        queue_repo, run_repo, _conversation, request = (
            await _require_owned_request_with_thread_lock(
                db=db, uid=uid, request_id=request_id,
            )
        )
        if request.status == "cancelled":
            await db.commit()
            return {"request_id": str(request.request_id), "status": "cancelled"}
        if request.status == "dispatched":
            await _raise_dispatched_conflict(run_repo, request_id)
        cancelled = await queue_repo.cancel_queued_request(request_id, uid=uid)
        if cancelled is None:
            await _raise_dispatched_conflict(run_repo, request_id)
        await db.commit()
        return {"request_id": str(cancelled.request_id), "status": "cancelled"}
    except Exception:
        await db.rollback()
        raise


async def steer_queued_request(
    *,
    db: AsyncSession,
    current_user: User,
    request_id: str,
) -> AgentRun | dict[str, Any]:
    """在会话行锁下将等待区请求升级为 steer，或在会话空闲时就地晋升执行。"""
    uid = str(current_user.uid)
    promoted_run: AgentRun | None = None
    try:
        queue_repo, run_repo, conversation, request = (
            await _require_owned_request_with_thread_lock(
                db=db, uid=uid, request_id=request_id,
            )
        )
        if request.status == "dispatched":
            await _raise_dispatched_conflict(run_repo, request_id)
        if request.status == "cancelled":
            raise AgentRunConflictError("请求已从等待区取消")
        thread_id = str(request.thread_id)
        if (
            await run_repo.get_pending_interaction_run(uid=uid, thread_id=thread_id)
            is not None
        ):
            raise AgentRunConflictError("当前会话有待回答的问题")
        active_run = await run_repo.get_latest_active_for_thread(
            uid=uid, thread_id=thread_id
        )
        if active_run is not None:
            upgraded = await queue_repo.upgrade_queued_to_steer(request_id, uid=uid)
            if upgraded is None:
                await _raise_dispatched_conflict(run_repo, request_id)
            position = await queue_repo.get_queue_position(
                thread_id, request_id, uid=uid
            )
            result = build_queued_response(upgraded, active_run, queue_position=position)
            await db.commit()
            return result
        promoted_run = await convert_request_to_run(db, request, conversation)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return await enqueue_committed_run(db, promoted_run)
