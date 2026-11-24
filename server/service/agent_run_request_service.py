from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from server.entities.agent import QueuedAgentRunResponse
from server.exception import AgentRunConflictError
from server.service.agent_run_request_queue_service import enqueue_committed_run
from server.service.arq_queue_servcie import enqueue_agent_run
from server.service.attachment_service import (
    attachment_file_ids,
    delete_copied_sources,
    delete_copied_targets,
    prepare_message_attachments,
)
from server.service.input_message_service import build_agent_input_msg
from src.database.models import AgentRun, AgentRunRequest, Conversation, User
from src.database.repositories import (
    AgentRepository,
    AgentRunRepository,
    AgentRunRequestQueueRepository,
    AgentRunRequestRepository,
    ConversationRepository,
    MessageAttachmentRepository,
)
from src.model import resolve_chat_model_selection, validate_model


async def create_agent_run_request(
    *,
    db: AsyncSession,
    conversation: Conversation,
    uid: str,
    user_id: int,
    agent_id: str,
    thread_id: str,
    request_id: str,
    query: str | None,
    request_metadata: dict[str, Any],
    image_content: str | None,
    dispatch_policy: str,
    active_run: AgentRun | None,
    copied_objects: list[tuple[str, str]],
) -> AgentRunRequest:
    """在会话行锁事务内校验模型、准备输入消息与附件，并持久化 AgentRunRequest。"""
    model_id = request_metadata.get("model")
    if model_id is not None and model_id != "" and not isinstance(model_id, str):
        raise ValueError("所选模型必须是字符串")
    # 控制字段由 Run/Conversation 持有，其余输入属性归 Message。
    msg_metadata = {
        key: value
        for key, value in request_metadata.items()
        if key not in {"type", "model", "request_id", "resume"}
    }
    file_ids = attachment_file_ids(msg_metadata)
    input_message = build_agent_input_msg(
        query=query or "",
        image_content=image_content,
        msg_metadata=msg_metadata,
    )
    agent = await AgentRepository(db).get_by_slug_for_run_type(
        slug=agent_id, run_type="chat"
    )
    if agent is None:
        raise LookupError("智能体不存在或已停用")
    conversation_repo = ConversationRepository(db)
    conversation_metadata = dict(conversation.conversation_metadata or {})
    model_id = resolve_chat_model_selection(
        model=model_id,
        conversation_model=conversation_metadata.get("model"),
        agent_model=(agent.agent_config or {}).get("model"),
    )
    await validate_model(db, model_id)
    if conversation_metadata.get("model") != model_id:
        conversation_metadata["model"] = model_id
        await conversation_repo.update_conversation(
            conversation,
            title=conversation.title,
            summary=conversation.summary,
            conversation_metadata=conversation_metadata,
        )
    attachments, new_copied = await prepare_message_attachments(
        db, user_id=user_id, thread_id=thread_id, file_ids=file_ids
    )
    copied_objects.extend(new_copied)
    message = await conversation_repo.create_agent_input_message(
        conversation_id=int(conversation.id),
        content=input_message.content,
        image_content=input_message.image_content,
        message_type=input_message.msg_type,
        request_id=request_id,
        msg_metadata=input_message.msg_metadata,
    )
    await MessageAttachmentRepository(db).create_links(
        message_id=int(message.id), attachments=attachments
    )
    queue_seq = (
        await AgentRunRequestQueueRepository(db).get_next_queue_seq(thread_id)
        if active_run is not None
        else None
    )
    request = await AgentRunRequestRepository(db).create_agent_run_request(
        request_id=request_id,
        uid=uid,
        thread_id=thread_id,
        agent_id=agent_id,
        trigger_message_id=int(message.id),
        dispatch_policy=dispatch_policy,
        status="queued" if active_run is not None else "dispatched",
        queue_seq=queue_seq,
    )
    if active_run is not None:
        message.status = "queued"
    return request


async def submit_agent_run_request(
    *,
    db: AsyncSession,
    current_user: User,
    query: str | None,
    agent_id: str,
    thread_id: str,
    request_metadata: dict[str, Any],
    image_content: str | None,
    dispatch_policy: str = "enqueue",
) -> AgentRun | QueuedAgentRunResponse:
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
    request_queue_repo = AgentRunRequestQueueRepository(db)
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
        agent_run_request = await agent_run_request_repo.get_run_request_by_request_id(request_id)
        existing_run = await agent_run_repo.get_run_by_request_id(request_id)
        for record in (agent_run_request, existing_run):
            if record is not None and (
                str(record.uid) != uid
                or str(record.thread_id) != thread_id
                or str(record.agent_id) != agent_id
            ):
                raise AgentRunConflictError("request_id 已被其他请求使用")
        if existing_run is not None:
            if existing_run.run_type != "chat":
                raise AgentRunConflictError("request_id 已被其他请求使用")
            await db.commit()
            return existing_run
        active_run = await agent_run_repo.get_latest_active_for_thread(
            uid=uid, thread_id=thread_id
        )
        if agent_run_request is not None and agent_run_request.status == "queued":
            position = await request_queue_repo.get_queue_position(
                thread_id, request_id, uid=uid,
            )
            result = QueuedAgentRunResponse.from_request(
                agent_run_request, active_run, queue_position=position
            )
            await db.commit()
            return result
        if agent_run_request is not None and agent_run_request.status == "cancelled":
            raise AgentRunConflictError("请求已从等待区取消")
        if (
            await agent_run_repo.get_pending_interaction_run(
                uid=uid, thread_id=thread_id
            )
            is not None
        ):
            raise AgentRunConflictError("当前会话有待回答的问题")
        if active_run is not None and dispatch_policy == "reject":
            raise AgentRunConflictError("当前会话有正在执行的任务")
        created_now = agent_run_request is None
        if created_now:
            agent_run_request = await create_agent_run_request(
                db=db,
                conversation=conversation,
                uid=uid,
                user_id=user_id,
                agent_id=agent_id,
                thread_id=thread_id,
                request_id=request_id,
                query=query,
                request_metadata=request_metadata,
                image_content=image_content,
                dispatch_policy=dispatch_policy,
                active_run=active_run,
                copied_objects=copied_objects,
            )
        if agent_run_request.status == "queued":
            position = await request_queue_repo.get_queue_position(
                thread_id, request_id, uid=uid,
            )
            result: AgentRun | QueuedAgentRunResponse = QueuedAgentRunResponse.from_request(
                agent_run_request, active_run, queue_position=position
            )
        else:
            run_metadata = {
                **dict(conversation.conversation_metadata or {}),
                "request_id": str(agent_run_request.request_id),
            }
            if not created_now:
                await validate_model(db, run_metadata.get("model"))
            result = await request_queue_repo.dispatch_request_to_run(
                request=agent_run_request,
                conversation=conversation,
                run_metadata=run_metadata,
            )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        await delete_copied_targets(copied_objects)
        # 不同会话的同名 request 不共用会话锁，主键唯一约束决定胜者。
        agent_run_request_record = await agent_run_request_repo.get_run_request_by_request_id(request_id)
        if agent_run_request_record is not None:
            await db.rollback()
            raise AgentRunConflictError("request_id 已被其他请求使用") from None
        raise
    except Exception:
        await db.rollback()
        await delete_copied_targets(copied_objects)
        raise
    await delete_copied_sources(copied_objects)
    return (
        result
        if isinstance(result, QueuedAgentRunResponse)
        else await enqueue_committed_run(db, result, enqueue_fn=enqueue_agent_run)
    )
