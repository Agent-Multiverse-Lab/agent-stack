from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from server.exception import AgentRunTimeOut
from server.service.arq_queue_servcie import (
    build_agent_chunk_envolope,
    enqueue_agent_run,
    publish_agent_run_cancel_signal,
    read_agent_run_stream_events,
    read_recent_agent_run_stream_events,
)
from server.service.attachment_service import (
    attachment_file_ids,
    delete_copied_sources,
    delete_copied_targets,
    prepare_message_attachments,
)
from server.service.input_message_service import build_agent_input_msg
from server.service.model_service import resolve_runtime_model
from server.utils.agent_run_utils import format_agent_run_sse
from src.database.models import AgentRun, AgentRunRequest, Conversation, User
from src.database.repositories import (
    AgentRepository,
    AgentRunRepository,
    AgentRunRequestRepository,
    ConversationRepository,
    MessageAttachmentRepository,
)
from src.database.session import session_context
from src.model import resolve_chat_model_selection
from src.utils import logger

_TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled", "interrupted"}
SUBAGENT_PROGRESS_EVENT_COUNT = 5


@dataclass(frozen=True)
class AgentRunRequestInput:
    """Run 创建业务接收的已保存请求及当前会话配置。"""

    request_id: str
    uid: str
    thread_id: str
    agent_id: str
    trigger_message_id: int
    conversation_metadata: dict[str, Any]


class AgentRunConflictError(RuntimeError):
    """Agent Run 当前状态不允许执行请求。"""

    def __init__(self, message: str, *, run_id: str | None = None) -> None:
        super().__init__(message)
        self.run_id = run_id


def _queued_response(
    request: AgentRunRequest,
    active_run: AgentRun | None = None,
    *,
    queue_position: int = 1,
) -> dict[str, Any]:
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


async def _queue_position(
    repo: AgentRunRequestRepository,
    *,
    thread_id: str,
    uid: str,
    request_id: str,
) -> int:
    queued = await repo.list_queued_for_thread(thread_id, uid=uid)
    for index, item in enumerate(queued, start=1):
        if str(item.request_id) == request_id:
            return index
    return len(queued) or 1


async def _create_request_run(db: AsyncSession, request: AgentRunRequest, conversation: Conversation) -> AgentRun:
    dispatch = AgentRunRequestInput(
        request_id=request.request_id, uid=request.uid, thread_id=request.thread_id,
        agent_id=request.agent_id, trigger_message_id=request.trigger_message_id,
        conversation_metadata=dict(conversation.conversation_metadata or {}),
    )
    metadata = {**dispatch.conversation_metadata, "request_id": dispatch.request_id}
    await resolve_runtime_model(db, metadata.get("model"))
    run = await AgentRunRepository(db).create_run(
        run_id=str(uuid.uuid4()), thread_id=dispatch.thread_id,
        conversation_id=int(conversation.id), uid=dispatch.uid, agent_slug=dispatch.agent_id,
        request_id=dispatch.request_id, trigger_message_id=dispatch.trigger_message_id,
        run_type="chat", run_metadata=metadata,
    )
    conversations = ConversationRepository(db)
    if request.status == "queued":
        await conversations.promote_queued_input_message(request.trigger_message_id, run.id)
        await AgentRunRequestRepository(db).mark_dispatched(request.request_id)
    else:
        await conversations.bind_input_message_to_run(run)
    return run


async def _enqueue_committed_run(db: AsyncSession, run: AgentRun) -> AgentRun:
    try:
        await enqueue_agent_run(str(run.id))
    except Exception as exc:
        logger.exception("Agent Run 入队失败：run_id=%s", run.id)
        failed_run, _ = await AgentRunRepository(db).set_agent_terminal(
            str(run.id), status="failed", error=f"Agent Run 入队失败：{exc}",
            error_type=type(exc).__name__,
        )
        await db.commit()
        return failed_run or run
    return run


async def create_agent_run_service(
    *, db: AsyncSession, current_user: User, query: str | None, agent_id: str,
    thread_id: str, request_metadata: dict[str, Any], image_content: str | None,
    dispatch_policy: str = "enqueue",
) -> AgentRun | dict:
    """持会话锁接收并分发请求，提交后才入 ARQ。"""
    if not thread_id:
        raise ValueError("会话 ID 不能为空")
    if request_metadata.get("type", "chat") != "chat":
        raise ValueError("普通创建接口要求 request_metadata.type 为 chat")
    if dispatch_policy not in {"enqueue", "reject", "steer"}:
        raise ValueError("无效的分发策略")
    uid, user_id = str(current_user.uid), int(current_user.id)
    request_id = str(request_metadata.get("request_id") or uuid.uuid4())
    conversation_repo = ConversationRepository(db)
    agent_run_request_repo = AgentRunRequestRepository(db)
    agent_run_repo = AgentRunRepository(db)
    copied_objects: list[tuple[str, str]] = []
    try:
        conversation = await conversation_repo.get_conversation_by_thread_id_for_user(
            thread_id=thread_id, user_id=uid, for_update=True,
        )
        if conversation is None:
            raise LookupError("当前会话不存在或已删除")
        if conversation.agent_id != agent_id:
            raise ValueError("当前会话未绑定所选智能体")
        request = await agent_run_request_repo.get_by_request_id(request_id)
        existing_run = await agent_run_repo.get_by_request_id(request_id)
        for record in (request, existing_run):
            if record is not None and (str(record.uid) != uid or str(record.thread_id) != thread_id or str(record.agent_id) != agent_id):
                raise AgentRunConflictError("request_id 已被其他请求使用")
        if existing_run is not None:
            if existing_run.run_type != "chat":
                raise AgentRunConflictError("request_id 已被其他请求使用")
            await db.commit()
            return existing_run
        active_run = await agent_run_repo.get_latest_active_for_thread(uid=uid, thread_id=thread_id)
        if request is not None and request.status == "queued":
            position = await _queue_position(
                agent_run_request_repo, thread_id=thread_id, uid=uid, request_id=request_id,
            )
            result = _queued_response(request, active_run, queue_position=position)
            await db.commit()
            return result
        if request is not None and request.status == "cancelled":
            raise AgentRunConflictError("请求已从等待区取消")
        if await agent_run_repo.get_pending_interaction_run(uid=uid, thread_id=thread_id) is not None:
            raise AgentRunConflictError("当前会话有待回答的问题")
        if active_run is not None and dispatch_policy == "reject":
            raise AgentRunConflictError("当前会话有正在执行的任务")
        if request is None:
            model_id = request_metadata.get("model")
            if model_id is not None and model_id != "" and not isinstance(model_id, str):
                raise ValueError("所选模型必须是字符串")
            # 控制字段由 Run/Conversation 持有，其余输入属性归 Message。
            msg_metadata = {
                key: value for key, value in request_metadata.items()
                if key not in {"type", "model", "request_id", "resume"}
            }
            file_ids = attachment_file_ids(msg_metadata)
            input_message = build_agent_input_msg(
                query=query or "", image_content=image_content, msg_metadata=msg_metadata,
            )
            agent = await AgentRepository(db).get_by_slug_for_run_type(slug=agent_id, run_type="chat")
            if agent is None:
                raise LookupError("智能体不存在或已停用")
            conversation_metadata = dict(conversation.conversation_metadata or {})
            model_id = resolve_chat_model_selection(
                model=model_id,
                conversation_model=conversation_metadata.get("model"),
                agent_model=(agent.agent_config or {}).get("model"),
            )
            await resolve_runtime_model(db, model_id)
            if conversation_metadata.get("model") != model_id:
                conversation_metadata["model"] = model_id
                await conversation_repo.update_conversation(
                    conversation,
                    title=conversation.title,
                    summary=conversation.summary,
                    conversation_metadata=conversation_metadata,
                )
            attachments, copied_objects = await prepare_message_attachments(
                db, user_id=user_id, thread_id=thread_id, file_ids=file_ids,
            )
            message = await conversation_repo.create_agent_input_message(
                conversation_id=int(conversation.id),
                content=input_message.content,
                image_content=input_message.image_content,
                message_type=input_message.msg_type,
                request_id=request_id,
                msg_metadata=input_message.msg_metadata,
            )
            await MessageAttachmentRepository(db).create_links(
                message_id=int(message.id), attachments=attachments,
            )
            request = await agent_run_request_repo.create_request(
                request_id=request_id,
                uid=uid,
                thread_id=thread_id,
                agent_id=agent_id,
                trigger_message_id=int(message.id),
                dispatch_policy=dispatch_policy,
                status="queued" if active_run is not None else "dispatched",
                queue_seq=await agent_run_request_repo.get_next_queue_seq(thread_id) if active_run is not None else None,
            )
            if active_run is not None:
                message.status = "queued"
        if request.status == "queued":
            position = await _queue_position(
                agent_run_request_repo, thread_id=thread_id, uid=uid, request_id=request_id,
            )
            result = _queued_response(request, active_run, queue_position=position)
        else:
            result = await _create_request_run(db, request, conversation)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        await delete_copied_targets(copied_objects)
        # 不同会话的同名 request 不共用会话锁，主键唯一约束决定胜者。
        record = await agent_run_request_repo.get_by_request_id(request_id)
        if record is not None:
            await db.rollback()
            raise AgentRunConflictError("request_id 已被其他请求使用") from None
        raise
    except Exception:
        await db.rollback()
        await delete_copied_targets(copied_objects)
        raise
    await delete_copied_sources(copied_objects)
    return result if isinstance(result, dict) else await _enqueue_committed_run(db, result)


async def dispatch_next_queued_request(thread_id: str) -> AgentRun | None:
    async with session_context() as db:
        # 与接收请求共用会话锁。
        conversation = await db.scalar(select(Conversation).where(
            Conversation.thread_id == thread_id, Conversation.deleted_at.is_(None),
        ).with_for_update())
        if conversation is None:
            return None
        runs = AgentRunRepository(db)
        if (await runs.get_latest_active_for_thread(uid=conversation.uid, thread_id=thread_id) is not None
                or await runs.get_pending_interaction_run(uid=conversation.uid, thread_id=thread_id) is not None):
            return None
        request = await AgentRunRequestRepository(db).pop_next_queued_for_thread(thread_id)
        if request is None:
            return None
        run = await _create_request_run(db, request, conversation)
        await db.commit()
        return await _enqueue_committed_run(db, run)


async def _require_owned_request_with_thread_lock(
    *,
    db: AsyncSession,
    uid: str,
    request_id: str,
) -> tuple[
    AgentRunRequestRepository,
    ConversationRepository,
    AgentRunRepository,
    Conversation,
    AgentRunRequest,
]:
    """校验等待区请求归属后持 Conversation FOR UPDATE 行锁复查最新状态。"""
    request_repo = AgentRunRequestRepository(db)
    conversation_repo = ConversationRepository(db)
    run_repo = AgentRunRepository(db)
    initial = await request_repo.get_by_request_id(request_id)
    if initial is None or str(initial.uid) != uid:
        raise LookupError("等待区请求不存在")
    conversation = await conversation_repo.get_conversation_by_thread_id_for_user(
        thread_id=str(initial.thread_id),
        user_id=uid,
        for_update=True,
    )
    if conversation is None:
        raise LookupError("当前会话不存在或已删除")
    request = await request_repo.get_by_request_id(request_id)
    if request is None or str(request.uid) != uid:
        raise LookupError("等待区请求不存在")
    return request_repo, conversation_repo, run_repo, conversation, request


async def _raise_dispatched_conflict(run_repo: AgentRunRepository, request_id: str) -> None:
    existing_run = await run_repo.get_by_request_id(request_id)
    raise AgentRunConflictError(
        "请求已开始执行",
        run_id=str(existing_run.id) if existing_run is not None else None,
    )


async def cancel_queued_agent_run_request_service(
    *,
    db: AsyncSession,
    current_user: User,
    request_id: str,
) -> dict[str, str]:
    """在会话行锁下逻辑软取消等待区请求及其未绑定输入消息。"""
    uid = str(current_user.uid)
    try:
        request_repo, conversation_repo, run_repo, _conversation, request = (
            await _require_owned_request_with_thread_lock(
                db=db, uid=uid, request_id=request_id,
            )
        )
        if request.status == "cancelled":
            await db.commit()
            return {"request_id": str(request.request_id), "status": "cancelled"}
        if request.status == "dispatched":
            await _raise_dispatched_conflict(run_repo, request_id)
        cancelled = await request_repo.cancel_queued_request(request_id, uid=uid)
        if cancelled is None:
            await _raise_dispatched_conflict(run_repo, request_id)
        await conversation_repo.cancel_queued_input_message(int(cancelled.trigger_message_id))
        await db.commit()
        return {"request_id": str(cancelled.request_id), "status": "cancelled"}
    except Exception:
        await db.rollback()
        raise


async def steer_queued_agent_run_request_service(
    *,
    db: AsyncSession,
    current_user: User,
    request_id: str,
) -> AgentRun | dict[str, Any]:
    """在会话行锁下将等待区请求升级为 steer，或在会话空闲时就地晋升执行。"""
    uid = str(current_user.uid)
    promoted_run: AgentRun | None = None
    try:
        request_repo, _conversation_repo, run_repo, conversation, request = (
            await _require_owned_request_with_thread_lock(
                db=db, uid=uid, request_id=request_id,
            )
        )
        if request.status == "dispatched":
            await _raise_dispatched_conflict(run_repo, request_id)
        if request.status == "cancelled":
            raise AgentRunConflictError("请求已从等待区取消")
        thread_id = str(request.thread_id)
        if await run_repo.get_pending_interaction_run(uid=uid, thread_id=thread_id) is not None:
            raise AgentRunConflictError("当前会话有待回答的问题")
        active_run = await run_repo.get_latest_active_for_thread(uid=uid, thread_id=thread_id)
        if active_run is not None:
            upgraded = await request_repo.upgrade_queued_to_steer(request_id, uid=uid)
            if upgraded is None:
                await _raise_dispatched_conflict(run_repo, request_id)
            position = await _queue_position(
                request_repo, thread_id=thread_id, uid=uid, request_id=request_id,
            )
            result = _queued_response(upgraded, active_run, queue_position=position)
            await db.commit()
            return result
        promoted_run = await _create_request_run(db, request, conversation)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return await _enqueue_committed_run(db, promoted_run)


async def create_resume_agent_run_service(
    *,
    db: AsyncSession,
    current_user: User,
    interrupted_run_id: str,
    agent_id: str,
    thread_id: str,
    request_metadata: dict[str, Any],
) -> AgentRun:
    if not thread_id:
        raise AgentRunConflictError("恢复请求的会话 ID 不能为空")
    if request_metadata.get("type") != "resume":
        raise ValueError("恢复接口要求 request_metadata.type 为 resume")

    run_metadata = dict(request_metadata)
    run_metadata.pop("type")
    resume = run_metadata.get("resume")
    if not isinstance(resume, dict):
        raise ValueError("request_metadata.resume 必须是对象")
    answers = resume.get("answers")
    if not isinstance(answers, dict) or not answers or not all(
        isinstance(key, str) and key and isinstance(value, str)
        for key, value in answers.items()
    ):
        raise ValueError("request_metadata.resume.answers 必须是非空回答字典")
    run_metadata["resume"] = {"answers": dict(answers)}
    request_id = str(run_metadata.get("request_id") or uuid.uuid4())
    run_metadata["request_id"] = request_id

    agent_run_repo = AgentRunRepository(db)
    owned_parent = await agent_run_repo.get_by_id_for_user(
        run_id=interrupted_run_id,
        uid=str(current_user.uid),
    )
    if owned_parent is None:
        raise LookupError("被打断的 Agent Run 不存在或不属于当前用户")
    if str(owned_parent.thread_id) != thread_id:
        raise AgentRunConflictError("恢复请求与父 Run 的会话不匹配")
    if str(owned_parent.agent_id) != agent_id:
        raise AgentRunConflictError("恢复请求与父 Run 的智能体不匹配")

    parent = await agent_run_repo.get_for_resume_for_update(
        run_id=interrupted_run_id,
        uid=str(current_user.uid),
        thread_id=thread_id,
    )
    if parent is None:
        raise AgentRunConflictError("父 Run 当前不可恢复")
    if str(parent.agent_status) != "interrupted":
        raise AgentRunConflictError("父 Run 不处于 interrupted 状态")

    interrupt_payload = dict(parent.run_metadata or {}).get("interrupt")
    questions = (
        interrupt_payload.get("questions")
        if isinstance(interrupt_payload, dict)
        else None
    )
    if not isinstance(questions, list) or not questions:
        raise ValueError("父 Run 缺少有效 questions")
    question_ids: set[str] = set()
    for question in questions:
        if not isinstance(question, dict):
            raise ValueError("父 Run 的问题结构无效")
        question_id = question.get("question_id")
        options = question.get("options")
        if (
            not isinstance(question_id, str) or not question_id
            or question_id in question_ids
            or not isinstance(question.get("question"), str)
            or not question["question"].strip()
            or not isinstance(options, list) or not options
            or not all(
                isinstance(option, dict)
                and isinstance(option.get("label"), str) and option["label"].strip()
                and isinstance(option.get("value"), str) and option["value"]
                for option in options
            )
        ):
            raise ValueError("父 Run 的问题或选项结构无效")
        question_ids.add(question_id)
        if answers.get(question_id) not in [option["value"] for option in options]:
            raise ValueError("回答不在父 Run 对应问题的选项中")
    if set(answers) != question_ids:
        raise ValueError("回答必须覆盖父 Run 的全部问题，且不能包含多余问题")

    existing = await agent_run_repo.get_resume_child(interrupted_run_id)
    if existing is not None:
        if str(existing.request_id) == request_id:
            if dict(existing.run_metadata or {}).get("resume", {}).get("answers") != answers:
                raise AgentRunConflictError("相同 request_id 不能提交不同回答")
            await db.commit()
            return existing
        raise AgentRunConflictError("当前问题已经回答")

    # 模型配置由父 Run 决定，回答请求不能替换模型。
    run_metadata.pop("model", None)
    parent_metadata = dict(parent.run_metadata or {})
    if "model" in parent_metadata:
        run_metadata["model"] = parent_metadata["model"]

    resume_run = await agent_run_repo.create_run(
        run_id=str(uuid.uuid4()),
        thread_id=str(parent.thread_id),
        conversation_id=int(parent.conversation_id),
        uid=str(parent.uid),
        agent_slug=str(parent.agent_id),
        request_id=request_id,
        trigger_message_id=None,
        run_type="resume",
        created_by_run_id=str(parent.id),
        run_metadata=run_metadata,
    )
    await db.commit()

    try:
        await enqueue_agent_run(str(resume_run.id))
    except Exception as exc:
        logger.exception("Resume Agent Run 入队失败：run_id=%s", resume_run.id)
        failed_run, _ = await agent_run_repo.set_agent_terminal(
            str(resume_run.id),
            status="failed",
            error=f"Resume Agent Run 入队失败：{exc}",
            error_type=type(exc).__name__,
        )
        await db.commit()
        if failed_run is not None:
            resume_run = failed_run
    return resume_run


async def load_agent_run_result(run_id: str, uid: str):
    return await get_agent_run_result(current_uid=uid, run_id=run_id)


async def wait_agent_run_result(run_id: str, uid: str, time_out: float = 600) -> str:
    """事件唤醒等待方，SQL 终态决定结果；超时与取消结束等待。"""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + time_out
    after_id = "0-0"
    while True:
        async with session_context() as db:
            run = await AgentRunRepository(db).get_by_id_for_user(run_id=run_id, uid=uid)
            if run is None:
                raise ValueError(f"Agent Run 不存在或不属于当前用户：{run_id}")
            status = str(run.agent_status)
            error = run.error
        if status == "completed":
            result = await load_agent_run_result(run_id=run_id, uid=uid)
            if result is None:
                raise RuntimeError(f"Agent Run 未保存最终消息：{run_id}")
            return result
        if status in _TERMINAL_RUN_STATUSES:
            raise RuntimeError(f"子 Agent Run {status}：{error or run_id}")
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise AgentRunTimeOut(run_id)
        try:
            events = await asyncio.wait_for(
                read_agent_run_events(
                    run_id, after_id=after_id, block_ms=max(1, min(1000, int(remaining * 1000)))
                ),
                timeout=remaining,
            )
        except TimeoutError as exc:
            raise AgentRunTimeOut(run_id) from exc
        if events:
            after_id = events[-1][0]
    

async def read_agent_run_events(
    run_id: str,
    *,
    after_id: str = "0-0",
    count: int | None = None,
    block_ms: int | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    rows = await read_agent_run_stream_events(
        run_id,
        after_id=after_id,
        count=count,
        block_ms=block_ms,
    )
    events: list[tuple[str, dict[str, Any]]] = []
    for _, stream_events in rows:
        for event_id, fields in stream_events:
            events.append((_to_text(event_id), _decode_event_fields(fields)))
    return events


async def read_subagent_progress(
    *,
    run_id: str,
    read_event_limit: int = SUBAGENT_PROGRESS_EVENT_COUNT,
) -> dict[str, Any]:
    """从 Redis Stream 读取子 Agent Run 状态和最近事件。"""

    if read_event_limit < 1:
        raise ValueError("read_event_limit 必须大于 0")

    subagent_event = await read_recent_agent_run_stream_events(
        run_id,
        count=read_event_limit,
    )
    events: list[dict[str, Any]] = []
    status = "running" if subagent_event else "pending"
    error: str | None = None
    for event_id, fields in reversed(subagent_event):
        envelope = _decode_event_fields(fields)
        event_payload = envelope.get("payload")
        payload = event_payload if isinstance(event_payload, dict) else {}
        event_status = payload.get("status")
        if isinstance(event_status, str) and event_status:
            status = event_status

        if payload.get("error") is not None:
            error = str(payload["error"])
        events.append(
            {
                "event_id": _to_text(event_id),
                "payload": envelope,
            }
        )

    return {
        "run_id": run_id,
        "status": status,
        "terminal": status in _TERMINAL_RUN_STATUSES,
        "error": error,
        "events": events,
    }


async def get_agent_run_result(
    *,
    current_uid: str,
    run_id: str,
) -> str | None:
    """按当前用户和 Run ID 从数据库读取最终 Agent 消息。"""

    async with session_context() as db:
        run = await AgentRunRepository(db).get_by_id_for_user(
            run_id=run_id,
            uid=current_uid,
        )
        if run is None:
            raise ValueError(f"Agent Run 不存在或不属于当前用户：{run_id}")
        if str(run.agent_status) != "completed":
            return None

        message = await ConversationRepository(db).get_run_result_message(run_id)
        if message is None:
            raise RuntimeError(f"Agent Run 未保存最终消息：{run_id}")
        return str(message.content)


async def stream_agent_run_events(
    *,
    run_id: str,
    current_uid: str,
    thread_id: str,
) -> AsyncIterator[str]:
    async with session_context() as db:
        run = await AgentRunRepository(db).get_by_id_for_user_and_thread(
            run_id=run_id,
            uid=current_uid,
            thread_id=thread_id,
        )
        if run is None:
            return

    after_id = "0-0"
    while True:
        events = await read_agent_run_events(run_id, after_id=after_id)
        for event_id, envelope in events:
            after_id = event_id
            yield format_agent_run_sse(event_id, envelope)
            if envelope.get("event_type") == "end":
                return

        if events:
            continue

        # Redis Stream 可能尚未创建、已经过期，或漏掉了终态事件；此时以数据库为准收口 SSE。
        async with session_context() as db:
            run = await AgentRunRepository(db).get_by_id_for_user_and_thread(
                run_id=run_id,
                uid=current_uid,
                thread_id=thread_id,
            )
            if run is None:
                return

            status = str(run.agent_status)
            if status == "completed":
                message = await ConversationRepository(db).get_run_result_message(
                    run_id
                )
                if message is not None:
                    yield format_agent_run_sse(
                        after_id,
                        build_agent_chunk_envolope(
                            run_id=run_id,
                            event_type="messages",
                            thread_id=thread_id,
                            payload={
                                "items": [
                                    {
                                        "event": "content-block-finish",
                                        "content": {"text": str(message.content)},
                                    }
                                ]
                            },
                            created_at=datetime.now(UTC).isoformat(),
                        ),
                    )
                yield format_agent_run_sse(
                    after_id,
                    build_agent_chunk_envolope(
                        run_id=run_id,
                        event_type="end",
                        thread_id=thread_id,
                        payload={"status": "completed"},
                        created_at=datetime.now(UTC).isoformat(),
                    ),
                )
                return

            if status in {"failed", "cancelled"}:
                yield format_agent_run_sse(
                    after_id,
                    build_agent_chunk_envolope(
                        run_id=run_id,
                        event_type="end",
                        thread_id=thread_id,
                        payload={
                            "status": status,
                            "error": str(run.error or status),
                        },
                        created_at=datetime.now(UTC).isoformat(),
                    ),
                )
                return

            if status == "interrupted":
                interrupt_payload = dict(run.run_metadata or {}).get("interrupt")
                if isinstance(interrupt_payload, dict):
                    yield format_agent_run_sse(
                        after_id,
                        build_agent_chunk_envolope(
                            run_id=run_id,
                            event_type="interrupt",
                            thread_id=thread_id,
                            payload={
                                **interrupt_payload,
                                "created_by_run_id": run_id,
                            },
                            created_at=datetime.now(UTC).isoformat(),
                        ),
                    )
                yield format_agent_run_sse(
                    after_id,
                    build_agent_chunk_envolope(
                        run_id=run_id,
                        event_type="end",
                        thread_id=thread_id,
                        payload={"status": "interrupted"},
                        created_at=datetime.now(UTC).isoformat(),
                    ),
                )
                return


async def cancel_run_service(
    *,
    run_id: str,
    current_user_id: str,
    db: AsyncSession,
) -> dict[str, str]:
    """取消当前用户的 Agent Run，并返回接口所需的运行信息。"""

    run = await request_cancel_agent_run(
        run_id=run_id,
        current_uid=current_user_id,
        db=db,
    )
    return {
        "run_id": str(run.id),
        "thread_id": str(run.thread_id),
        "agent_id": str(run.agent_id),
        "status": str(run.agent_status),
    }


async def request_cancel_agent_run(
    *,
    run_id: str,
    current_uid: str,
    db: AsyncSession,
    allow_subagent: bool = False,
) -> AgentRun:
    """持久化目标 Agent Run 及其活跃子 Run 的取消请求。"""

    signal_run_ids: list[str] = []
    run_repository = AgentRunRepository(db)
    run = await run_repository.get_by_id_for_user(
        run_id=run_id,
        uid=current_uid,
    )
    if run is None:
        raise ValueError(f"Agent Run 不存在或不属于当前用户：{run_id}")
    if not allow_subagent and str(getattr(run, "run_type", "chat")) == "subagent":
        raise AgentRunConflictError("子智能体运行不支持直接取消，请取消父智能体运行")

    if hasattr(run_repository, "cascade_cancel_descendants"):
        child_signal_ids = await run_repository.cascade_cancel_descendants(
            [run_id]
        )
        signal_run_ids.extend(child_signal_ids)
    else:
        child_runs = await run_repository.list_active_child_runs(
            created_by_run_id=run_id,
            uid=current_uid,
        )
        for child_run in child_runs:
            child_run = await run_repository.request_cancel(str(child_run.id))
            if (
                child_run is not None
                and str(child_run.agent_status) == "cancel_requested"
            ):
                signal_run_ids.append(str(child_run.id))

    run = await run_repository.request_cancel(run_id)
    if run is None:
        raise ValueError(f"Agent Run 不存在：{run_id}")
    if str(run.agent_status) == "cancel_requested":
        signal_run_ids.append(run_id)

    # Redis 信号只能在取消状态持久化成功后发布，避免 Worker 先收到信号。
    await db.commit()

    await asyncio.gather(
        *(
            publish_agent_run_cancel_signal(signal_run_id)
            for signal_run_id in signal_run_ids
        )
    )
    return run


def _decode_event_fields(fields: dict[Any, Any]) -> dict[str, Any]:
    raw_event = fields.get("event") if "event" in fields else fields.get(b"event")
    if raw_event is None:
        return {}
    if isinstance(raw_event, bytes):
        raw_event = raw_event.decode()
    event = json.loads(raw_event)
    return event if isinstance(event, dict) else {"data": event}


def _to_text(value: Any) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)
