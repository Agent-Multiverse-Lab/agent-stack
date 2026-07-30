import asyncio
import sys
from collections.abc import AsyncIterator
from typing import Any

from arq.connections import RedisSettings
from langchain_core.messages import AIMessage, BaseMessageChunk
from sqlalchemy import select

from server.service.agent_run_service import publish_agent_run_event
from server.service.arq_queue_servcie import (
    clear_agent_run_cancel_signal,
    has_agent_run_cancel_signal,
)
from server.service.input_message_service import build_agent_input_msg
from server.service.thread_service import stream_agent_response
from src.agents import agent_manager
from src.configs import config
from src.database import postgres_manager
from src.database.models import AgentRun, Message, User
from src.database.repositories import (
    AgentRepository,
    AgentRunRepository,
    ConversationRepository,
)
from src.utils import logger

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

RUN_CANCEL_POLL_SECONDS = 0.2


class AgentRunCancelRequested(Exception):
    """Worker 收到已落库 Run 的取消信号。"""




async def ensure_agents_exist() -> None:
    """只补充缺失的代码注册 Agent，不刷新已有数据库记录。"""

    agents = agent_manager.list_top_level_agents()
    subagents = agent_manager.list_subagents()
    async with postgres_manager.get_async_session_context() as session:
        repository = AgentRepository(session)
        for agent in agents:
            await repository.ensure_agent_registered(
                slug=agent["id"],
                backend_id=agent["id"],
                name=agent["name"],
                description=agent["description"],
                role="orchestrator",
                internal_only=False,
            )
        for agent in subagents:
            await repository.ensure_agent_registered(
                slug=agent["name"],
                backend_id=agent["id"],
                name=agent["name"],
                description=agent["description"],
                role="subagent",
                internal_only=True,
            )
    logger.info(
        "Worker 已确保数据库表及 Agent 注册：top=%s, subagents=%s",
        ", ".join(item["id"] for item in agents),
        ", ".join(item["name"] for item in subagents),
    )


async def startup(ctx) -> None:
    """初始化 worker 数据库资源，并单点确保表和固定 Agent 注册。"""

    await postgres_manager.initialize()
    try:
        await postgres_manager.ensure_tables_exist()
        await ensure_agents_exist()
    except Exception:
        await postgres_manager.dispose()
        raise


async def shutdown(ctx) -> None:
    """Worker 退出时只释放自己持有的 PostgreSQL 资源。"""

    await postgres_manager.dispose()


async def set_run_running(run_id: str) -> AgentRun | None:
    # FIXME: Worker 开始执行时单独设置 running 状态。
    async with postgres_manager.get_async_session_context() as db:
        agent_run_repo = AgentRunRepository(db)
        return await agent_run_repo.set_running(run_id)


async def set_run_completed(
    run_id: str,
    *,
    conversation_id: int,
    content: str,
) -> AgentRun | None:
    async with postgres_manager.get_async_session_context() as db:
        agent_run_repo = AgentRunRepository(db)
        run = await agent_run_repo.set_completed(run_id)
        if run is None or str(run.agent_status) != "completed":
            return run

        await ConversationRepository(db).create_agent_output_message(
            conversation_id=conversation_id,
            agent_run_id=run_id,
            content=content,
        )
        return run


async def set_run_failed(run_id: str, error: str) -> AgentRun | None:
    # FIXME: Worker 执行失败时单独设置 failed 状态。
    async with postgres_manager.get_async_session_context() as db:
        agent_run_repo = AgentRunRepository(db)
        return await agent_run_repo.set_failed(run_id, error)


async def set_run_cancelled(run_id: str) -> AgentRun | None:
    # FIXME: Worker 被打断时单独设置 cancelled 状态。
    async with postgres_manager.get_async_session_context() as db:
        agent_run_repo = AgentRunRepository(db)
        return await agent_run_repo.set_cancelled(run_id)




async def _get_user(uid: str) -> User | None:
    """获取到当前前的user
    """
    async with postgres_manager.get_async_session_context() as db:
        result = await db.execute(select(User).where(User.uid == uid))
        return result.scalar_one_or_none()

async def _get_agent_input_msg(message_id: int | None) -> Message | None:
    async with postgres_manager.get_async_session_context() as db:
        result = await db.execute(select(Message).where(Message.id == message_id))
        return result.scalar_one_or_none()


async def _get_agent_run(run_id: str):
    async with postgres_manager.get_async_session_context() as db:
        agent_run_repo = AgentRunRepository(db)
        return await agent_run_repo.get_by_id(run_id)


async def _wait_for_cancel_signal(run_id: str) -> None:
    while not await has_agent_run_cancel_signal(run_id):
        await asyncio.sleep(RUN_CANCEL_POLL_SECONDS)


async def _consume_stream_with_cancel(
    stream: AsyncIterator[tuple[str, Any]],
    *,
    run_id: str,
) -> AsyncIterator[tuple[str, Any]]:
    cancel_task = asyncio.create_task(_wait_for_cancel_signal(run_id))
    next_task: asyncio.Task | None = None
    try:
        while True:
            next_task = asyncio.create_task(stream.__anext__())
            done, _ = await asyncio.wait(
                {next_task, cancel_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if cancel_task in done:
                cancel_task.result()
                next_task.cancel()
                await asyncio.gather(next_task, return_exceptions=True)
                raise AgentRunCancelRequested(run_id)

            try:
                yield next_task.result()
            except StopAsyncIteration:
                return
    finally:
        for task in (next_task, cancel_task):
            if task is not None and not task.done():
                task.cancel()
        await asyncio.gather(
            *(task for task in (next_task, cancel_task) if task is not None),
            return_exceptions=True,
        )


async def _finalize_cancelled_run(
    run_id: str,
    *,
    thread_id: str,
) -> dict[str, str]:
    run = await set_run_cancelled(run_id)
    if run is None:
        raise ValueError(f"Agent Run 不存在：{run_id}")

    status = str(run.agent_status)
    try:
        if status == "cancelled":
            await publish_agent_run_event(
                run_id,
                {
                    "type": "end",
                    "status": "cancelled",
                    "thread_id": thread_id,
                },
            )
    finally:
        await clear_agent_run_cancel_signal(run_id)
    return {"run_id": run_id, "status": status}


async def _finalize_failed_run(
    run_id: str,
    *,
    thread_id: str,
    error: str,
) -> dict[str, str]:
    run = await set_run_failed(run_id, error)
    if run is None:
        raise ValueError(f"Agent Run 不存在：{run_id}")

    status = str(run.agent_status)
    if status == "cancel_requested":
        return await _finalize_cancelled_run(run_id, thread_id=thread_id)
    if status == "failed":
        try:
            await publish_agent_run_event(
                run_id,
                {
                    "type": "end",
                    "status": "failed",
                    "thread_id": thread_id,
                    "error": error,
                },
            )
        except Exception:
            logger.exception(f"Agent run 错误事件发布失败：{run_id}")
    return {"run_id": run_id, "status": status}


async def write_agent_run_event(
    run_id: str,
    payload: Any,
    event_type: str,
    thread_id: str,
) -> None:
    await publish_agent_run_event(
        run_id,
        {
            "type": event_type,
            "thread_id": thread_id,
            "payload": payload,
        },
    )


class StreamEventSmoother:
    """按字符阈值合并并发布连续的消息流事件。"""

    def __init__(
        self,
        *,
        thread_id: str,
        run_id: str,
        character_limit: int,
    ) -> None:
        """初始化单个 Agent Run 的消息缓冲池。"""

        if character_limit < 1:
            raise ValueError("character_limit 必须大于 0")

        self.thread_id = thread_id
        self.run_id = run_id
        self.character_limit = character_limit
        self.buffer_pool: list[
            tuple[BaseMessageChunk, dict[str, Any]]
        ] = []

    async def buffer(
        self,
        payload: tuple[BaseMessageChunk, dict[str, Any]],
    ) -> None:
        """缓冲消息 chunk，达到字符阈值后立即释放。"""

        chunk, metadata = payload
        if self.buffer_pool:
            buffered_chunk, buffered_metadata = self.buffer_pool[-1]
            if (
                type(buffered_chunk) is not type(chunk)
                or buffered_chunk.id != chunk.id
                or buffered_metadata.get("namespace") != metadata.get("namespace")
                or buffered_metadata.get("langgraph_node")
                != metadata.get("langgraph_node")
            ):
                await self.release()

        self.buffer_pool.append(payload)
        buffered_characters = sum(
            len(message_chunk.text)
            for message_chunk, _ in self.buffer_pool
        )
        if buffered_characters >= self.character_limit:
            await self.release()

    async def release(self) -> None:
        """将缓冲池合并为一条 messages 事件并写入 Redis Stream。"""

        if not self.buffer_pool:
            return

        merged_chunk, _ = self.buffer_pool[0]
        for chunk, _ in self.buffer_pool[1:]:
            merged_chunk = merged_chunk + chunk
        metadata = self.buffer_pool[-1][1]

        await write_agent_run_event(
            run_id=self.run_id,
            payload=(merged_chunk, metadata),
            event_type="messages",
            thread_id=self.thread_id,
        )
        self.buffer_pool.clear()


async def process_agent_run(ctx, run_id: str):
    agent_run_event: AgentRun | None = await _get_agent_run(run_id)
    if agent_run_event is None:
        logger.error(f"当前agent运行id：{run_id} 不存在")
        return

    # FIXME: agent_status 是当前 run 生命周期的事实字段，避免再读取旧 status 默认值。
    initial_status = str(agent_run_event.agent_status)
    if initial_status in {"completed", "failed", "cancelled"}:
        return {"run_id": run_id, "status": initial_status}
    if initial_status == "cancel_requested":
        return await _finalize_cancelled_run(
            run_id,
            thread_id=str(agent_run_event.thread_id),
        )

    agent_input_message = await _get_agent_input_msg(
        message_id=agent_run_event.trigger_message_id  # ty:ignore[invalid-argument-type]
    )  # ty:ignore[invalid-argument-type]
    if agent_input_message is None:
        error_message = (
            f"Input message not found: {agent_run_event.trigger_message_id}"
        )
        logger.error(
            f"当前agent运行id：{run_id} 的输入消息不存在："
            f"{agent_run_event.trigger_message_id}"
        )
        return await _finalize_failed_run(
            run_id,
            thread_id=str(agent_run_event.thread_id),
            error=error_message,
        )

    # 构建agent内部的参数
    uid = agent_run_event.uid
    agent_slug = agent_run_event.agent_id
    request_id = agent_run_event.request_id
    thread_id = agent_run_event.thread_id

    image_content = agent_input_message.image_content  # ty:ignore[unresolved-attribute]

    # 构建访问消息
    agent_input_message_formatted = build_agent_input_msg(
        query=agent_input_message.content,  # ty:ignore[invalid-argument-type]
        # FIXME: 恢复数据库里记录的输入消息类型，而不是传空字符串。
        msg_type=agent_input_message.message_type,  # ty:ignore[invalid-argument-type]
        image_content=image_content,  # ty:ignore[invalid-argument-type]
    )

    # 配置整体metadata
    user = await _get_user(uid=uid)  # ty:ignore[invalid-argument-type]

    if not user:
        error_message = f"User not found: {uid}"
        return await _finalize_failed_run(
            run_id,
            thread_id=str(thread_id),
            error=error_message,
        )

    # Run 类型由创建入口显式落库；parent_run_id 只保留运行间的关联关系。
    run_type = str(agent_run_event.run_type)
    metadata = {
        "run_id": run_id,
        "request_id": request_id,
        "agent_slug": agent_slug,
        "thread_id": thread_id,
        "uid": user.uid,  # ty:ignore[unresolved-attribute]
        "run_type": run_type,
    }

    running_run = await set_run_running(run_id)
    if running_run is None:
        raise ValueError(f"Agent Run 不存在：{run_id}")
    running_status = str(running_run.agent_status)
    if running_status == "cancel_requested":
        return await _finalize_cancelled_run(
            run_id,
            thread_id=str(thread_id),
        )
    if running_status in {"completed", "failed", "cancelled"}:
        return {"run_id": run_id, "status": running_status}

    await publish_agent_run_event(
        run_id,
        {
            "type": "status",
            "status": "running",
            "thread_id": thread_id,
        },
    )
    result_text = ""
    stream_event_smoother = StreamEventSmoother(
        thread_id=str(thread_id),
        run_id=run_id,
        character_limit=20,
    )
    try:
        try:
            async with postgres_manager.get_async_session_context() as db:
                stream_thread_events: AsyncIterator = stream_agent_response(
                    agent_slug=agent_slug,  # ty:ignore[invalid-argument-type]
                    thread_id=thread_id,  # ty:ignore[invalid-argument-type]
                    runtime_metadata=metadata,
                    thread_input_message=agent_input_message_formatted,
                    current_user=user,
                    db=db,
                )

                async for event_type, payload in _consume_stream_with_cancel(
                    stream_thread_events,
                    run_id=run_id,
                ):
                    if event_type == "values":
                        messages = payload["messages"]
                        if messages and isinstance(messages[-1], AIMessage):
                            result_text = str(messages[-1].text)
                    logger.info(
                        f"Agent run 事件输出：run_id={run_id}, "
                        f"event_type={event_type}, payload={payload}"
                    )
                    if event_type == "messages":
                        await stream_event_smoother.buffer(payload)
                        continue

                    await stream_event_smoother.release()
                    await write_agent_run_event(
                        run_id=run_id,
                        payload=payload,
                        event_type=event_type,
                        thread_id=thread_id,  # ty:ignore[invalid-argument-type]
                    )
        finally:
            await stream_event_smoother.release()
    except AgentRunCancelRequested:
        logger.info(f"Agent run 收到取消请求：{run_id}")
        return await _finalize_cancelled_run(
            run_id,
            thread_id=str(thread_id),
        )
    except Exception as exc:
        result = await _finalize_failed_run(
            run_id,
            thread_id=str(thread_id),
            error=str(exc),
        )
        if result["status"] != "failed":
            return result
        logger.exception(f"Agent run 执行失败：{run_id}")
        raise

    if await has_agent_run_cancel_signal(run_id):
        return await _finalize_cancelled_run(
            run_id,
            thread_id=str(thread_id),
        )

    completed_run = await set_run_completed(
        run_id,
        conversation_id=int(agent_run_event.conversation_id),
        content=result_text,
    )
    if completed_run is None:
        raise ValueError(f"Agent Run 不存在：{run_id}")
    completed_status = str(completed_run.agent_status)
    if completed_status == "cancel_requested":
        return await _finalize_cancelled_run(
            run_id,
            thread_id=str(thread_id),
        )
    if completed_status != "completed":
        return {"run_id": run_id, "status": completed_status}

    await publish_agent_run_event(
        run_id,
        {
            "type": "end",
            "status": "completed",
            "thread_id": thread_id,
        },
    )
    return {"run_id": run_id, "status": "completed"}



class WorkerSettings:
    functions = [process_agent_run]
    queue_name = config.arq_queue_name
    redis_settings = RedisSettings.from_dsn(config.redis_url)
    max_jobs = config.arq_max_jobs
    on_startup = startup
    on_shutdown = shutdown
