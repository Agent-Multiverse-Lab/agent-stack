from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from server.service.arq_queue_servcie import (
    build_agent_chunk_envolope,
    get_arq_pool,
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
from server.utils.agent_run_utils import format_agent_run_sse
from src.configs import config
from src.database.models import AgentRun, User
from src.database.repositories import (
    AgentRunRepository,
    ConversationRepository,
    MessageAttachmentRepository,
)
from src.database.session import session_context
from src.utils import logger

_TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled"}
SUBAGENT_PROGRESS_EVENT_COUNT = 5


async def create_agent_run_service(
    *,
    db: AsyncSession,
    current_user: User,
    query: str | None,
    agent_id: str,
    thread_id: str,
    thread_metadata: dict[str, Any],
    image_content: str | None,
    parent_run_id: str | None,
    msg_metadata: dict[str, Any],
) -> AgentRun:
    """原子创建用户消息和 Agent Run，提交后入队。"""
    if not thread_id:
        raise ValueError("会话 ID 不能为空")

    file_ids = attachment_file_ids(msg_metadata)
    input_message = build_agent_input_msg(
        query=query or "",
        image_content=image_content,
        msg_metadata=msg_metadata,
    )

    conversation_repository = ConversationRepository(db)
    conversation = await conversation_repository.get_conversation_by_thread_id_for_user(
        thread_id=thread_id,
        user_id=str(current_user.uid),
    )
    if conversation is None:
        raise LookupError("当前会话不存在或已删除")

    run_metadata = dict(thread_metadata)
    request_id = str(run_metadata.get("request_id") or uuid.uuid4())
    run_id = str(uuid.uuid4())
    copied_objects: list[tuple[str, str]] = []

    try:
        attachments, copied_objects = await prepare_message_attachments(
            db,
            user_id=int(current_user.id),
            thread_id=thread_id,
            file_ids=file_ids,
        )
        message = await conversation_repository.create_agent_input_message(
            conversation_id=int(conversation.id),
            content=input_message.content,
            image_content=input_message.image_content,
            message_type=input_message.msg_type,
            request_id=request_id,
            msg_metadata=input_message.msg_metadata,
        )
        await MessageAttachmentRepository(db).create_links(
            message_id=int(message.id),
            attachments=attachments,
        )
        run = await AgentRunRepository(db).create_run(
            run_id=run_id,
            thread_id=thread_id,
            conversation_id=int(conversation.id),
            uid=str(current_user.uid),
            agent_slug=agent_id,
            request_id=request_id,
            trigger_message_id=int(message.id),
            run_type="chat",
            parent_run_id=parent_run_id,
            run_metadata=run_metadata,
        )
        message.agent_run_id = run.id
        await db.flush()
        await db.commit()
    except Exception:
        await db.rollback()
        await delete_copied_targets(copied_objects)
        raise

    await delete_copied_sources(copied_objects)
    try:
        await enqueue_agent_run(str(run.id))
    except Exception as exc:
        logger.exception("Agent Run 入队失败：run_id=%s", run.id)
        failed_run = await AgentRunRepository(db).set_agent_terminal(
            str(run.id),
            status="failed",
            error=f"Agent Run 入队失败：{exc}",
            error_type=type(exc).__name__,
        )
        if failed_run is not None:
            run = failed_run
        await db.commit()
    return run


async def enqueue_agent_run(run_id: str) -> None:
    queue = await get_arq_pool()
    # FIXME: enqueue 必须写入与 WorkerSettings.queue_name 相同的 ARQ 队列。
    logger.info(f"当前事件 ID：{run_id}入队中...")
    await queue.enqueue_job(
        "process_agent_run",
        run_id,
        _job_id=f"run:{run_id}",
        _queue_name=config.arq_queue_name,
    )


async def wait_agent_run_result(run_id: str) -> str:
    """从数据库等待 Run 终态并读取最终消息。"""
    while True:
        async with session_context() as db:
            run = await AgentRunRepository(db).get_by_id(run_id)
            if run is None:
                raise ValueError(f"Agent Run 不存在：{run_id}")

            status = str(run.agent_status)
            if status == "completed":
                message = await ConversationRepository(db).get_run_result_message(
                    run_id
                )
                if message is None:
                    raise RuntimeError(f"Agent Run 未保存最终消息：{run_id}")
                return str(message.content)
            if status in {"failed", "cancelled"}:
                raise RuntimeError(str(run.error or status))

        await asyncio.sleep(1)


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

    child_runs = await run_repository.list_active_child_runs(
        parent_run_id=run_id,
        uid=current_uid,
    )
    for child_run in child_runs:
        child_run = await run_repository.request_cancel(str(child_run.id))
        if child_run is not None and str(child_run.agent_status) == "cancel_requested":
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
