import base64
import binascii
import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from langchain.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from server.service.input_message_service import AgentInputMsg
from server.utils.auth import AuthenticatedUser
from src.agents import agent_manager
from src.agents.base_agent import BaseAgent
from src.configs import config
from src.database import (
    Agent,
    AgentRun,
    Attachment,
    Conversation,
    Message,
    MessageAttachment,
    User,
)
from src.database.repositories import (
    AgentRepository,
    AgentRunRepository,
    ConversationRepository,
    MessageAttachmentRepository,
    UserRepository,
)
from src.storage import get_storage

_THREAD_CURSOR_VERSION = 1
_SYSTEM_THREAD_METADATA_KEYS = frozenset({"backend_id"})


class ThreadConflictError(RuntimeError):
    """对话操作与当前运行状态冲突。"""


async def create_thread(
    db: AsyncSession,
    *,
    uid: str,
    agent_id: str,
    title: str | None,
    summary: str | None,
    metadata: dict[str, Any] | None,
) -> Conversation:
    """创建当前用户绑定顶层 Agent 的对话。"""
    user = await UserRepository(db).get_by_uid(uid)
    if user is None:
        raise LookupError("用户不存在")

    agent = await AgentRepository(db).get_by_slug_for_run_type(
        slug=agent_id,
        run_type="chat",
    )
    if agent is None:
        raise LookupError("智能体不存在")

    title_text = (title or "").strip() or "新对话"
    summary_text = summary.strip() if summary is not None else None
    thread_metadata = dict(metadata or {})
    thread_metadata["backend_id"] = str(agent.backend_id)

    return await ConversationRepository(db).create_conversation(
        uid=uid,
        thread_id=str(uuid.uuid4()),
        agent_slug=str(agent.slug),
        title=title_text,
        summary=summary_text,
        conversation_metadata=thread_metadata,
    )


async def list_threads(
    db: AsyncSession,
    *,
    uid: str,
    limit: int,
    cursor: str | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    """分页列出或搜索当前用户的顶层对话。"""
    query_text = None
    if query is not None:
        query_text = query.strip()
        if not query_text:
            raise ValueError("对话搜索词不能为空")

    before_activity_at = None
    before_id = None
    if cursor is not None:
        before_activity_at, before_id = _decode_cursor(cursor)

    rows = await ConversationRepository(db).list_top_level_for_user(
        uid=uid,
        limit=limit + 1,
        query=query_text,
        before_activity_at=before_activity_at,
        before_id=before_id,
    )
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = None
    if has_more and page:
        conversation, _, last_activity_at = page[-1]
        next_cursor = _encode_cursor(
            last_activity_at,
            int(conversation.id),
        )

    return {
        "items": [
            _thread_summary(conversation, last_message_at)
            for conversation, last_message_at, _ in page
        ],
        "next_cursor": next_cursor,
    }


async def get_thread_detail(
    db: AsyncSession,
    *,
    uid: str,
    thread_id: str,
    message_limit: int,
    before_message_id: int | None = None,
) -> dict[str, Any]:
    """加载指定顶层对话及一页持久化消息。"""
    conversations = ConversationRepository(db)
    conversation = await _require_thread(conversations, uid, thread_id)
    messages_desc = await conversations.list_messages(
        conversation_id=int(conversation.id),
        limit=message_limit + 1,
        before_message_id=before_message_id,
    )
    has_more = len(messages_desc) > message_limit
    page_desc = messages_desc[:message_limit]
    next_before_message_id = (
        int(page_desc[-1].id) if has_more and page_desc else None
    )

    run_ids = list(
        {
            str(message.agent_run_id)
            for message in page_desc
            if message.agent_run_id is not None
        }
    )
    runs = await AgentRunRepository(db).get_by_ids_for_conversation(
        run_ids=run_ids,
        conversation_id=int(conversation.id),
    )
    attachment_rows = await MessageAttachmentRepository(
        db
    ).list_attachments_by_message_ids(
        [int(message.id) for message in page_desc]
    )
    message_attachments = await _message_attachment_payloads(attachment_rows)
    last_message_at = await conversations.get_last_message_at(
        conversation_id=int(conversation.id)
    )

    return {
        "thread": _thread_summary(conversation, last_message_at),
        "messages": [
            _message_response(
                message,
                runs,
                message_attachments.get(int(message.id), []),
            )
            for message in reversed(page_desc)
        ],
        "next_before_message_id": next_before_message_id,
    }


async def update_thread(
    db: AsyncSession,
    *,
    uid: str,
    thread_id: str,
    fields: set[str],
    title: str | None,
    summary: str | None,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    """更新当前用户对话的可变字段。"""
    allowed_fields = {"title", "summary", "metadata"}
    if not fields or not fields.issubset(allowed_fields):
        raise ValueError("未提供可更新的对话字段")

    conversations = ConversationRepository(db)
    conversation = await _require_thread(conversations, uid, thread_id)
    title_text = str(conversation.title)
    summary_text = (
        str(conversation.summary)
        if conversation.summary is not None
        else None
    )
    existing_metadata = dict(conversation.conversation_metadata or {})
    thread_metadata = dict(existing_metadata)

    if "title" in fields:
        if title is None or not title.strip():
            raise ValueError("对话标题不能为空")
        title_text = title.strip()
    if "summary" in fields:
        summary_text = summary.strip() if summary is not None else None
    if "metadata" in fields:
        if metadata is None:
            raise ValueError("对话 metadata 必须是对象")
        thread_metadata = dict(metadata)
        for key in _SYSTEM_THREAD_METADATA_KEYS:
            if key in existing_metadata:
                thread_metadata[key] = existing_metadata[key]
            else:
                thread_metadata.pop(key, None)

    conversation = await conversations.update_conversation(
        conversation,
        title=title_text,
        summary=summary_text,
        conversation_metadata=thread_metadata,
    )
    last_message_at = await conversations.get_last_message_at(
        conversation_id=int(conversation.id)
    )
    return _thread_summary(conversation, last_message_at)


async def delete_thread(
    db: AsyncSession,
    *,
    uid: str,
    thread_id: str,
) -> None:
    """确认没有活动 Run 后软删除根对话及内部子对话。"""
    conversations = ConversationRepository(db)
    conversation = await _require_thread(conversations, uid, thread_id)
    conversation_tree = await conversations.list_tree_for_user(
        root_conversation_id=int(conversation.id),
        uid=uid,
    )
    conversation_ids = [int(item.id) for item in conversation_tree]
    if await AgentRunRepository(db).has_active_for_conversations(
        conversation_ids=conversation_ids,
        uid=uid,
    ):
        raise ThreadConflictError("当前对话仍有未结束的 Agent Run")

    await conversations.soft_delete_tree(
        conversation_ids=conversation_ids,
        uid=uid,
    )


async def _require_thread(
    conversations: ConversationRepository,
    uid: str,
    thread_id: str,
) -> Conversation:
    """读取当前用户未删除的顶层对话。"""
    conversation = await conversations.get_top_level_for_user(
        uid=uid,
        thread_id=thread_id,
    )
    if conversation is None:
        raise LookupError("当前会话不存在或已删除")
    return conversation


def _thread_summary(
    conversation: Conversation,
    last_message_at: datetime | None,
) -> dict[str, Any]:
    """构建对话列表和详情共用字段。"""
    return {
        "thread_id": str(conversation.thread_id),
        "title": str(conversation.title),
        "summary": (
            str(conversation.summary)
            if conversation.summary is not None
            else None
        ),
        "agent_id": str(conversation.agent_id),
        "metadata": dict(conversation.conversation_metadata or {}),
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "last_message_at": last_message_at,
    }


async def _message_attachment_payloads(
    rows: list[tuple[MessageAttachment, Attachment]],
) -> dict[int, list[dict[str, Any]]]:
    """按消息分组并生成可用附件的短时访问 URL。"""
    storage = get_storage()
    access_urls: dict[int, str] = {}
    grouped: dict[int, list[dict[str, Any]]] = {}
    for link, attachment in rows:
        attachment_id = int(attachment.id)
        available = attachment.deleted_at is None
        access_url = None
        if available:
            access_url = access_urls.get(attachment_id)
            if access_url is None:
                access_url = await storage.create_file_access_url(
                    config.attachment_bucket,
                    str(attachment.original_object_name),
                )
                access_urls[attachment_id] = access_url

        grouped.setdefault(int(link.message_id), []).append(
            {
                "id": str(attachment.file_id),
                "file_name": str(attachment.attachment_name),
                "content_type": str(attachment.attachment_type),
                "file_size": int(attachment.attachment_size),
                "status": str(attachment.status),
                "available": available,
                "access_url": access_url,
            }
        )
    return grouped


def _message_response(
    message: Message,
    runs: dict[str, AgentRun],
    attachments: list[dict[str, Any]],
) -> dict[str, Any]:
    """组装消息和对应的持久化 Run 元数据。"""
    run = (
        runs.get(str(message.agent_run_id))
        if message.agent_run_id is not None
        else None
    )
    run_payload = None
    if run is not None:
        run_payload = {
            "run_id": str(run.id),
            "run_type": str(run.run_type),
            "status": str(run.agent_status),
            "parent_run_id": (
                str(run.parent_run_id)
                if run.parent_run_id is not None
                else None
            ),
            "metadata": dict(run.run_metadata or {}),
            "started_at": run.started_at,
            "finished_at": run.finished_at,
        }

    return {
        "message_id": int(message.id),
        "role": str(message.role),
        "content": str(message.content),
        "image_content": (
            str(message.image_content)
            if message.image_content is not None
            else None
        ),
        "message_type": str(message.message_type or "text"),
        "status": str(message.status),
        "request_id": (
            str(message.request_id)
            if message.request_id is not None
            else None
        ),
        "run": run_payload,
        "attachments": attachments,
        "created_at": message.created_at,
        "updated_at": message.updated_at,
    }


def _encode_cursor(activity_at: datetime, conversation_id: int) -> str:
    """编码稳定且不透明的对话列表游标。"""
    payload = json.dumps(
        {
            "version": _THREAD_CURSOR_VERSION,
            "activity_at": activity_at.isoformat(),
            "conversation_id": conversation_id,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, int]:
    """校验并解码对话列表游标。"""
    try:
        padding = "=" * (-len(cursor) % 4)
        raw = base64.b64decode(
            (cursor + padding).encode(),
            altchars=b"-_",
            validate=True,
        )
        payload = json.loads(raw.decode())
        if (
            not isinstance(payload, dict)
            or payload.get("version") != _THREAD_CURSOR_VERSION
        ):
            raise ValueError

        activity_at = datetime.fromisoformat(payload["activity_at"])
        conversation_id = int(payload["conversation_id"])
        if activity_at.tzinfo is None or conversation_id <= 0:
            raise ValueError
        return activity_at, conversation_id
    except (
        binascii.Error,
        KeyError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
    ) as exc:
        raise ValueError("无效的对话列表游标") from exc


async def _build_agent_runtime(
    agent_slug: str,
    user: User,
    thread_id: str | None,
    db: AsyncSession,
    run_type: str = "chat",
) -> tuple[Any, BaseAgent]:
    """根据传递的参数，构建 agent 基础以及实例

    Args:
        agent_id (str): agent name
        user (User): 当前用户可访问的agent
        thread_id (str | None): _description_
        run_type: Agent Run 类型，当前为 chat 或 subagent

    Returns:
        tuple[Any, Any, Any]: _description_
    """
    agent_repo = AgentRepository(db)

    if not agent_slug:
        raise ValueError("未配置agent")

    agent = await agent_repo.get_by_slug_for_run_type(
        slug=agent_slug, run_type=run_type
    )

    if not agent:
        raise ValueError("当前智能体不存在")

    agent_instance: BaseAgent = agent_manager.get_agent(
        agent_id=agent.backend_id  # ty:ignore[invalid-argument-type]
    )

    if not agent_instance:
        raise ValueError("当前Agent实例不存在")

    return agent, agent_instance


async def _build_agent_runtime_context(
    agent_instance: BaseAgent,
    uid: str,
    run_id: str,
    thread_id: str,
    request_id: str,
):
    """结合前端传递构建 agent 运行的固有参数的上下文

    Args:
        agent_instance (BaseAgent): 当前要触发的 agent上下文实例
        uid (str): 当前用户id
        run_id (str): 当前运行agent事件的id
        thread_id (str): 当前会话的id
        request_id (str): 当前会话内的单词请求id

    Returns:
        dict[str, str]: 上下文结构
    """
    agent_runtime_context = {}
    
    # 构建固有上下文元素
    # agent_runtime_context = agent_instance.agent_context()

    # 根据当前用户的传递内容填填充上下文
    agent_runtime_context.update(
        {
            "uid": uid,
            "run_id": run_id,
            "thread_id": thread_id,
            "request_id": request_id,
        }
    )
    return agent_runtime_context


async def _check_conv_status(
    *, conv_repo: ConversationRepository, thread_id: str, uid: str, agent_item: Agent
):
    """确保当前的conv存在"""
    # FIXME: run 只能使用已经创建且属于当前用户的 Conversation。
    current_conv = await conv_repo.get_conversation_by_thread_id_for_user(
        thread_id=thread_id,
        user_id=uid,
    )
    if not current_conv:
        raise ValueError(f"当前会话不存在：{thread_id}")
    if current_conv.agent_id != agent_item.slug:
        raise ValueError(f"当前会话未绑定智能体：{agent_item.slug}")

    # TODO 其他的错点


async def stream_agent_response(
    *,
    agent_slug: str,
    thread_id: str,
    runtime_metadata: dict,
    thread_input_message: AgentInputMsg,
    current_user: AuthenticatedUser,
    db: AsyncSession,
) -> AsyncIterator[Any]:
    """前端发送的内容产生消息流

    Args:
        agent_id (str): agent的名称
        thread_id (str): 当前会话的id
        thread_input_message (str): 输入的消息
        current_user (AuthenticatedUser): 当前用户
        db (AsyncSession): 数据库session
        metadata (dict[str, Any] | None, optional): 附带的信息，如agent类型，本此请求的等

    Returns:
        AsyncIterator[bytes]: _description_
    """
    # guard
    if not thread_id:
        thread_id = str(uuid.uuid4())

    runtime_metadata = dict(runtime_metadata or {})

    # 设置单次 request_id 作为单次断联的标志以及附件的隔离归属
    if not runtime_metadata.get("request_id"):
        runtime_metadata["request_id"] = str(uuid.uuid4())

    # 抽取agent执行的元数据
    query: str = thread_input_message.content
    image_content: str | None = thread_input_message.image_content
    human_msg: HumanMessage = thread_input_message.langchain_msg

    # 根据agent_id解析 agent 的运行配置

    agent_item, agent_instacne = await _build_agent_runtime(
        agent_slug=agent_slug,
        user=current_user,
        thread_id=thread_id,
        db=db,
        run_type=runtime_metadata.get("run_type") or "chat",
    )

    runtime_metadata.update(
        {
            "query": query,
            "agent_slug": agent_item.slug,
            "agent_instance": agent_instacne,
            "thread_id": thread_id,
            "uid": current_user.uid,
            "has_image": bool(image_content),
        }
    )

    messages = [human_msg]
    agent_runtime_context = await _build_agent_runtime_context(
        agent_instance=agent_instacne,
        uid=current_user.uid,  # ty:ignore[invalid-argument-type]
        run_id=runtime_metadata.get("run_id"),  # ty:ignore[invalid-argument-type]
        thread_id=thread_id,
        request_id=runtime_metadata.get(
            "request_id"
        ),  # ty:ignore[invalid-argument-type]
    )

    # 确保当前的会话存在
    conv_repo = ConversationRepository(db)

    await _check_conv_status(
        conv_repo=conv_repo,
        thread_id=thread_id,
        uid=current_user.uid,  # ty:ignore[invalid-argument-type]
        agent_item=agent_item,
    )

    # TODO确保文件相关存在，此处按下不表

    # FIXME: 通过 runtime_context 传值，避免把 context 重复透传给 astream_events。
    async for method, payload in agent_instacne.stream_messages_with_event(
        messages,  # ty:ignore[invalid-argument-type]
        runtime_context=agent_runtime_context,
    ):
        if method in {"messages", "values", "agent_execute_event"}:
            yield method, payload

        #  if mode == "values":
        #         agent_state = extract_agent_state(payload if isinstance(payload, dict) else {})
        #         signature = _agent_state_signature(agent_state)
        #         if signature and signature != last_agent_state_signature:
        #             last_agent_state_signature = signature
        #             yield make_chunk(status="agent_state", agent_state=agent_state, meta=meta)
        #         continue
