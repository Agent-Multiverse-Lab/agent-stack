from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from server.exception import AgentRunConflictError, AgentRunTimeOut
from server.service.arq_queue_servcie import (
    build_agent_chunk_envolope,
    enqueue_agent_run,
    publish_agent_run_cancel_signal,
    read_agent_run_stream_events,
    read_recent_agent_run_stream_events,
)
from server.utils.agent_run_utils import format_agent_run_sse
from src.database.models import AgentRun, User
from src.database.repositories import (
    AgentRunRepository,
    ConversationRepository,
)
from src.database.session import session_context
from src.utils import logger

_TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled", "interrupted"}
SUBAGENT_PROGRESS_EVENT_COUNT = 5


async def create_resume_agent_run(
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

async def cancel_agent_run(
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
