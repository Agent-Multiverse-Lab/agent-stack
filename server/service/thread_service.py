import base64
import binascii
import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from langchain.messages import HumanMessage
from langchain_core.messages import AIMessageChunk
from sqlalchemy.ext.asyncio import AsyncSession

from server.service.input_message_service import AgentInputMsg
from server.utils import reslove_thread_id
from server.utils.auth import AuthenticatedUser
from src.agents import BaseAgent, agent_manager
from src.agents import CustomAgentState as AgentState
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
from src.storage.minio import ATTACHMENT_BUCKET_NAME
from src.utils import logger

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
    next_before_message_id = int(page_desc[-1].id) if has_more and page_desc else None

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
    ).list_attachments_by_message_ids([int(message.id) for message in page_desc])
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
        str(conversation.summary) if conversation.summary is not None else None
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
            str(conversation.summary) if conversation.summary is not None else None
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
                    ATTACHMENT_BUCKET_NAME,
                    str(attachment.object_name),
                )
                access_urls[attachment_id] = access_url

        grouped.setdefault(int(link.message_id), []).append(
            {
                "file_id": str(attachment.file_id),
                "file_name": str(attachment.file_name),
                "content_type": str(attachment.content_type),
                "file_size": int(attachment.file_size),
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
                str(run.parent_run_id) if run.parent_run_id is not None else None
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
            str(message.image_content) if message.image_content is not None else None
        ),
        "message_type": str(message.message_type or "text"),
        "status": str(message.status),
        "request_id": (
            str(message.request_id) if message.request_id is not None else None
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


def _make_stream_msg_key(
    agent_metadata: dict | None, thread_id: str | None
) -> tuple[str, str]:
    # 从langchain的原生消息拿到生成的id,如果没有就直接拿thread_id替代
    if not isinstance(agent_metadata, dict):
        return thread_id or "", ""
    return thread_id or "", str(agent_metadata.get("run_id", ""))


def _assign_stream_msg_id(
    message_ids: dict[tuple[str, str], str],
    key: tuple[str, str],
    llm_og_msg_id: str | None = None,
) -> str:
    if llm_og_msg_id:
        message_ids[key] = llm_og_msg_id
        return llm_og_msg_id
    return message_ids.setdefault(key, str(uuid.uuid4()))


def _reslove_agent_state(agent_state: dict):
    agent_result: AgentState = {"agent_todo": list(agent_state.get("todos") or [])}
    return agent_result


def _lc_message_v2_dispather(
    agent_msg: dict[str, Any], *, message_id: str, thread_id: str | None
) -> list[dict[str, Any]]:
    """将 langchain v2 的消息事件转换为标准化的消息事件"""
    events = []
    content = agent_msg.get("content")
    reasoning_content = agent_msg.get("reasoning_content")
    additional_kwargs = (
        agent_msg.get("additional_kwargs")
        if isinstance(agent_msg.get("additional_kwargs"), dict)
        else {}
    )
    additional_kwargs_reasoning_content = additional_kwargs.get("reasoning_content")

    message_event: dict[str, Any] = {
        "type": "message_delta",
        "message_id": message_id,
        "thread_id": thread_id,
    }
    message_event["cotent_delta"] = content if isinstance(content, str) else None
    message_event["reasoning_content_delta"] = (
        reasoning_content
        if isinstance(reasoning_content, str) and reasoning_content
        else None
    )
    message_event["additional_kwargs_reasoning_content"] = (
        additional_kwargs_reasoning_content
        if isinstance(additional_kwargs_reasoning_content, str)
        and additional_kwargs_reasoning_content
        else None
    )

    if tool_call_chunks := agent_msg.get("tool_call_chunks"):
        if isinstance(tool_call_chunks, list):
            for tool_call_chunk in tool_call_chunks:
                if not isinstance(tool_call_chunk, dict):
                    continue
                if tool_call_chunk.get("args") is not None and isinstance(
                    tool_call_chunk.get("args"), str
                ):
                    args = json.dumps(tool_call_chunk.get("args"), ensure_ascii=False)
                else:
                    args = None

                if (
                    not tool_call_chunk.get("id")
                    and not tool_call_chunk.get("name")
                    and not args
                ):
                    continue

                events.append(
                    {
                        "type": "tool_call",
                        "message_id": message_id,
                        "thread_id": thread_id,
                        "tool_call_id": str(tool_call_chunk.get("id")),
                        "name": str(tool_call_chunk.get("name")),
                        "args": args,
                        "index": int(tool_call_chunk.get("index", 0)),
                    }
                )


def _lc_message_v3_dispather(
    event: dict[str, Any], *, message_id: str, thread_id: str | None
) -> dict[str, Any] | None:

    # v3版本尚未稳定，后续会将整套消息协议直接迁移，
    # 按照目前的设计方式来说，大家好像现在也不执着于
    # to show the reasoning process, because a lot of agent products prefer directly showing the input state and the output state，Maybe with some summary

    event_type = event.get("event")
    if (
        event_type in ("message-start", "content-block-start", "message-finish")
        or not message_id
    ):
        return None

    if event_type == "content-block-delta":
        delta = event.get("delta") if isinstance(event.get("delta"), dict) else None
        text = delta.get("text")
        if delta.get("type") == "text-delta" and isinstance(text, str) and text:
            return {
                "type": "message_delta",
                "message_id": message_id,
                "content_delta": text,
                "thread_id": thread_id,
            }
        return None

    if event_type == "content-block-finish":
        # 专门处理工具的调用完成的事件， 这个时候，event里面会有一个content字段，里面包含了工具调用的结果
        content = (
            event.get("content") if isinstance(event.get("content"), str) else None
        )
        if (
            event.get("type") != "tool_call"
            or not event.get("id")
            and content.get("name")
        ):
            return None

        return {
            "type": "tool_call",
            "message_id": message_id,
            "thread_id": thread_id,
            "tool_call_id": content.get("id"),
            "name": content.get("name"),
            "args": content.get("args") if content.get("args") else {},
            "index": event.get("index") if event.get("index") is not None else 0,
        }


def _make_lc_message_to_standard(
    agent_msg: dict[str, Any] | Any,
    *,
    agent_metadata: dict[str, Any] | None,
    thread_id: str | None,
    message_ids: dict[tuple[str, str], str],
) -> list[dict[str, Any]]:
    # 构建消息ID
    stream_msg_key = _make_stream_msg_key(agent_metadata, thread_id)

    # 兼容v3的格式
    if isinstance(agent_msg, dict) and isinstance(agent_msg.get("event"), str):
        # message-start', 'role': 'ai', 'id': 'lc_run--019fe66c-12dd-7e33-9785-49084a241a6e' start的id会串联整个执行周期的整体文件
        if agent_msg.get("event") == "message-start" and agent_msg.get("id"):
            llm_og_msg_id = str(agent_msg.get("id"))
        else:
            llm_og_msg_id = None
        message_id: str = _assign_stream_msg_id(
            message_ids, stream_msg_key, llm_og_msg_id
        )
        standard_stream_event = _lc_message_v3_dispather(
            event=agent_msg, message_id=message_id, thread_id=thread_id
        )
        return (
            [standard_stream_event] if standard_stream_event else []
        )  # ty: ignore[invalid-return-type]

    # 初始的v2的格式
    if isinstance(agent_msg, AIMessageChunk):
        agent_msg_dict = agent_msg.model_dump()
    elif isinstance(agent_msg, dict):
        agent_msg_dict = dict(agent_msg)
    else:
        agent_msg_dict = {"content": str(agent_msg)}

    message_id: str = str(agent_msg_dict.get("id")) or _assign_stream_msg_id(
        message_ids, stream_msg_key
    )
    return _lc_message_v2_dispather(
        agent_msg=agent_msg_dict, message_id=message_id, thread_id=thread_id
    )


def _serialize_agent_state(agent_state: AgentState | None) -> str:
    if not agent_state:
        return ""
    try:
        agent_state = json.dumps(agent_state, ensure_ascii=False, sort_keys=True)
        return agent_state
    except Exception:
        return str(agent_state)


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

    # 统一消息传递格式
    def make_agent_stream_event(
        status: str | None = None,
        content: Any = None,
        **kwargs: Any,
    ) -> bytes:
        """构建 agent 流式输出的事件格式"""
        thread_id = (
            kwargs.pop("thread_id", None)
            or runtime_metadata.get("thread_id")
            or thread_id
        )
        return (
            json.dumps(
                {
                    "request_id": runtime_metadata.get("request_id"),
                    "response": content,
                    "thread_id": thread_id,
                    "status": status,
                    **kwargs,
                },
                ensure_ascii=False,
            ).encode("utf-8")
            + b"\n"
        )

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

    # 根据agent_id解析 agent 的运行配置，构建agent实例
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
            "thread_id": thread_id,
            "uid": current_user.uid,
            "has_image": bool(image_content),
        }
    )

    # 构建构建agentu运行所需的上下文
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

    # agent任务执行任务状态
    last_agent_state = ""
    message_ids: dict[tuple[str, str], str] = {}

    try:
        # 构建运行中所需的repo
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
            if method == "values":
                try:
                    agent_state = _reslove_agent_state(payload)
                    currentr_agent_state = _serialize_agent_state(agent_state)
                    if (
                        currentr_agent_state
                        and currentr_agent_state != last_agent_state
                    ):
                        last_agent_state = currentr_agent_state
                        yield make_agent_stream_event(
                            status="agent_state",
                            content=agent_state,
                            runtime_metadata=runtime_metadata,
                        )
                    continue
                except Exception:
                    import traceback

                    print(traceback.print_exc())

            if method == "agent_execute_state":
                yield make_agent_stream_event(
                    status="agent_execute_state",
                    event=payload,
                    namespace=(
                        payload.get("namespace") if isinstance(payload, dict) else []
                    ),
                    thread_id=(
                        payload.get("thread_id")
                        if isinstance(payload, dict)
                        else thread_id
                    ),
                    runtime_metadata=runtime_metadata,
                )
                continue

            # message输出的时候走的路径
            agent_msg, agent_metadata = payload
            agent_msg_thread_id = reslove_thread_id(agent_metadata, thread_id)
            standard_stream_events = _make_lc_message_to_standard(
                agent_msg=agent_msg,
                agent_metadata=agent_metadata,
                thread_id=thread_id,
                message_ids=message_ids,
            )

            for standard_stream_event in standard_stream_events:
                if standard_stream_event.get("type") != "message_delta":
                    content = ""
                else:
                    content = standard_stream_event.get("cotent_delta", "")

                yield make_agent_stream_event(
                    status="loading",
                    content=content,
                    stream_event=standard_stream_events,
                    metadata=agent_metadata,
                    thread_id=thread_id,
                )

        yield make_agent_stream_event(
            status="finished",
            runtime_metadata=runtime_metadata,
        )
    except Exception as e:
        import traceback

        logger.exception(f"{traceback.print_exc()}")


async def stream_resume_response():
    # TODO interrupt后的断续重连
    pass
