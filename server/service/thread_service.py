import base64
import binascii
import json
import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from langchain.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from server.service.input_message_service import AgentInputMsg
from server.utils.auth import AuthenticatedUser
from src.agents import agent_manager
from src.agents.base_agent import BaseAgent
from src.database import Agent, AgentRun, Conversation, Message, User
from src.database.repositories import (
    AgentRepository,
    AgentRunRepository,
    AttachmentRepository,
    ConversationRepository,
    UserRepository,
)
from src.storage import get_storage, sanitize_filename

TMP_ATTACHMENT_PREFIX = "tmp"
CHAT_ATTACHMENT_PREFIX = "save"
_THREAD_CURSOR_VERSION = 1
_SYSTEM_THREAD_METADATA_KEYS = frozenset({"backend_id"})


class ThreadConflictError(RuntimeError):
    """对话操作与当前运行状态冲突。"""


class ThreadService:
    """协调 Thread/Conversation 的创建、查询、更新和删除。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.agents = AgentRepository(db)
        self.runs = AgentRunRepository(db)
        self.conversations = ConversationRepository(db)
        self.users = UserRepository(db)

    async def create_thread(
        self,
        *,
        uid: str,
        agent_id: str,
        title: str | None,
        summary: str | None,
        metadata: dict[str, Any] | None,
    ) -> Conversation:
        """创建当前用户绑定顶层 Agent 的对话。"""
        user = await self.users.get_by_uid(uid)
        if user is None:
            raise LookupError("用户不存在")

        agent = await self.agents.get_by_slug_for_run_type(
            slug=agent_id,
            run_type="chat",
        )
        if agent is None:
            raise LookupError("智能体不存在")

        title_text = (title or "").strip() or "新对话"
        summary_text = summary.strip() if summary is not None else None
        thread_metadata = dict(metadata or {})
        thread_metadata["backend_id"] = str(agent.backend_id)

        return await self.conversations.create_conversation(
            uid=uid,
            thread_id=str(uuid.uuid4()),
            agent_slug=str(agent.slug),
            title=title_text,
            summary=summary_text,
            conversation_metadata=thread_metadata,
        )

    async def list_threads(
        self,
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
            before_activity_at, before_id = self._decode_cursor(cursor)

        rows = await self.conversations.list_top_level_for_user(
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
            next_cursor = self._encode_cursor(
                last_activity_at,
                int(conversation.id),
            )

        return {
            "items": [
                self._thread_summary(conversation, last_message_at)
                for conversation, last_message_at, _ in page
            ],
            "next_cursor": next_cursor,
        }

    async def get_thread_detail(
        self,
        *,
        uid: str,
        thread_id: str,
        message_limit: int,
        before_message_id: int | None = None,
    ) -> dict[str, Any]:
        """加载指定顶层对话及一页持久化消息。"""
        conversation = await self._require_thread(uid, thread_id)
        messages_desc = await self.conversations.list_messages(
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
        runs = await self.runs.get_by_ids_for_conversation(
            run_ids=run_ids,
            conversation_id=int(conversation.id),
        )
        last_message_at = await self.conversations.get_last_message_at(
            conversation_id=int(conversation.id)
        )

        return {
            "thread": self._thread_summary(
                conversation,
                last_message_at,
            ),
            "messages": [
                self._message_response(message, runs)
                for message in reversed(page_desc)
            ],
            "next_before_message_id": next_before_message_id,
        }

    async def update_thread(
        self,
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

        conversation = await self._require_thread(uid, thread_id)
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

        conversation = await self.conversations.update_conversation(
            conversation,
            title=title_text,
            summary=summary_text,
            conversation_metadata=thread_metadata,
        )
        last_message_at = await self.conversations.get_last_message_at(
            conversation_id=int(conversation.id)
        )
        return self._thread_summary(conversation, last_message_at)

    async def delete_thread(self, *, uid: str, thread_id: str) -> None:
        """确认没有活动 Run 后软删除根对话及内部子对话。"""
        conversation = await self._require_thread(uid, thread_id)
        conversation_tree = await self.conversations.list_tree_for_user(
            root_conversation_id=int(conversation.id),
            uid=uid,
        )
        conversation_ids = [int(item.id) for item in conversation_tree]
        if await self.runs.has_active_for_conversations(
            conversation_ids=conversation_ids,
            uid=uid,
        ):
            raise ThreadConflictError("当前对话仍有未结束的 Agent Run")

        await self.conversations.soft_delete_tree(
            conversation_ids=conversation_ids,
            uid=uid,
        )

    async def _require_thread(
        self,
        uid: str,
        thread_id: str,
    ) -> Conversation:
        """读取当前用户未删除的顶层对话。"""
        conversation = await self.conversations.get_top_level_for_user(
            uid=uid,
            thread_id=thread_id,
        )
        if conversation is None:
            raise LookupError("当前会话不存在或已删除")
        return conversation

    @staticmethod
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

    @staticmethod
    def _message_response(
        message: Message,
        runs: dict[str, AgentRun],
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
            "created_at": message.created_at,
            "updated_at": message.updated_at,
        }

    @staticmethod
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

    @staticmethod
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


def build_tmp_attachment_file_key(user_id: str, filename: str) -> str:
    """生成当前用户的临时会话附件对象路径。"""
    return (
        f"{TMP_ATTACHMENT_PREFIX}/{user_id}/chat/attachment/"
        f"{uuid.uuid4().hex}/{sanitize_filename(filename or 'file')}"
    )


def build_conversation_attachment_file_key(
    user_id: str,
    conversation_id: str | int,
    attachment_id: str | int,
    filename: str,
) -> str:
    """生成已经归属对话的附件对象路径。"""
    return (
        f"{CHAT_ATTACHMENT_PREFIX}/{user_id}/chat/{conversation_id}/"
        f"attachment/{attachment_id}/{sanitize_filename(filename or 'file')}"
    )


async def prepare_attachments_for_conversation(
    db: AsyncSession,
    *,
    user_id: str,
    conversation_id: str,
    attachments: Sequence[object] | None = None,
) -> list[dict[str, object]]:
    """将当前用户的临时附件绑定到指定对话。"""
    repository = AttachmentRepository(session=db)
    attachment_records: list[dict[str, object]] = []

    for attachment in attachments or []:
        attachment_data = (
            attachment.model_dump()
            if hasattr(attachment, "model_dump")
            else attachment
        )
        if not isinstance(attachment_data, dict):
            continue

        attachment_id = str(attachment_data.get("id") or "")
        attachment_record = await repository.get_by_id_for_user(
            attachment_id,
            user_id,
        )
        if attachment_record is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Attachment not found.",
            )

        file_name = attachment_record.attachment_name
        content_type = (
            attachment_record.attachment_type or "application/octet-stream"
        )
        file_size = attachment_record.attachment_size
        parse_status = attachment_data.get("parse_status")
        parse_error = attachment_data.get("parse_error")
        parser = attachment_data.get("parser")
        category = attachment_data.get("category")
        if category not in {"image", "document"}:
            category = (
                "image" if content_type.startswith("image/") else "document"
            )
        parse_metadata = attachment_data.get("parse_metadata")
        parsed_text = attachment_data.get("parsed_text")

        file_key = attachment_record.attachment_path
        if attachment_record.status == "pending":
            if _is_tmp_file_key(user_id, file_key):
                file_key = build_conversation_attachment_file_key(
                    user_id,
                    conversation_id,
                    attachment_record.id,
                    file_name,
                )
                await _copy_attachment(
                    attachment_record.attachment_path,
                    file_key,
                    content_type,
                )
            await repository.mark_attached(
                attachment_record,
                conversation_id=conversation_id,
                attachment_path=file_key,
            )
        elif attachment_record.status not in {"pending", "attached"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Attachment status is invalid.",
            )

        access_url = await get_storage().create_file_access_url(
            "knowledgebases",
            file_key,
        )

        attachment_records.append(
            {
                "id": str(attachment_record.id),
                "file_name": file_name,
                "content_type": content_type,
                "file_size": file_size,
                "file_key": file_key,
                "category": category,
                "access_url": access_url,
                "parser": parser,
                "parse_status": parse_status,
                "parse_error": parse_error,
                "parse_metadata": parse_metadata,
                "parsed_text": parsed_text,
            }
        )

    return attachment_records


def _is_tmp_file_key(user_id: str, file_key: str) -> bool:
    """判断对象路径是否属于当前用户的临时附件目录。"""
    return file_key.startswith(
        f"{TMP_ATTACHMENT_PREFIX}/{user_id}/chat/attachment/"
    )


async def _copy_attachment(
    source_file_key: str,
    destination_file_key: str,
    content_type: str,
) -> None:
    """将临时附件复制到对话持久路径。"""
    content = await get_storage().download_file(
        "knowledgebases",
        source_file_key,
    )
    await get_storage().upload_file(
        "knowledgebases",
        destination_file_key,
        content,
        content_type or "application/octet-stream",
    )
