import asyncio
import json
import sys
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from arq.connections import RedisSettings
from sqlalchemy import select

from server.service.arq_queue_servcie import (
    RUN_REDIS_TTL_SECONDS,
    clear_agent_run_cancel_signal,
    has_agent_run_cancel_signal,
    wait_agent_run_cancel_signal,
    write_agent_run_stream_event,
)
from server.service.input_message_service import build_agent_input_msg
from server.service.thread_service import stream_agent_response
from server.utils.woker_utils import reslove_thread_id
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


@dataclass
class AgentRunContext:
    """持有单个 Agent Run 的进程内取消监听状态。"""

    run_id: str
    _cancel_event: asyncio.Event = field(
        default_factory=asyncio.Event,
        init=False,
    )
    _cancel_listener_task: asyncio.Task[None] | None = field(
        default=None,
        init=False,
    )

    def start(self) -> None:
        """启动当前 Run 唯一的 Redis 取消信号监听任务。"""

        if self._cancel_listener_task is not None:
            return
        self._cancel_listener_task = asyncio.create_task(
            self._watch_cancel_signal()
        )

    async def wait_cancel_signal(self) -> None:
        """等待当前 Run 的取消信号，并传播监听任务异常。"""

        listener_task = self._cancel_listener_task
        if listener_task is None:
            raise RuntimeError("Agent Run 取消信号监听尚未启动")

        await self._cancel_event.wait()
        await listener_task

    async def close(self) -> None:
        """取消并等待当前 Run 的 Redis 取消信号监听任务。"""

        listener_task = self._cancel_listener_task
        if listener_task is None:
            return
        if not listener_task.done():
            listener_task.cancel()
        await asyncio.gather(listener_task, return_exceptions=True)

    async def _watch_cancel_signal(self) -> None:
        try:
            await wait_agent_run_cancel_signal(self.run_id)
        finally:
            # 正常取消或监听异常都要唤醒等待方，由等待方取得任务结果。
            self._cancel_event.set()


async def ensure_agents_exist() -> None:
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
        await postgres_manager.setup_langgraph_persistence()
        await ensure_agents_exist()
    except Exception:
        logger.exception("Worker 启动资源初始化失败")
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


async def set_run_terminal(
    run_id: str,
    *,
    status: str,
    error: str | None = None,
    error_type: str | None = None,
) -> tuple[str | None, bool]:
    """用于agent的run事件的结束(无论何种状态), 当状态确实改变后,改变agent的状态,
    """
    async with postgres_manager.get_async_session_context() as db:
        agent_run_repo = AgentRunRepository(db)
        run, changed = await agent_run_repo.set_agent_terminal(
            run_id,
            status=status,
            error=error,
            error_type=error_type,
        )

        current_agent_status = str(run.agent_status) if run else None
        return current_agent_status, changed


async def _get_user(uid: str) -> User | None:
    """获取到当前前的user"""
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


async def _cancellable_stream(
    stream: AsyncIterator[tuple[str, Any]],
    *,
    run_context: AgentRunContext,
) -> AsyncIterator[tuple[str, Any]]:
    """逐条消费 Agent 流，并等待 Run Context 的取消信号。"""
    while True:
        cancel_task = asyncio.create_task(run_context.wait_cancel_signal())
        stream_task = asyncio.create_task(anext(stream))
        done, _ = await asyncio.wait(
                                {stream_task, cancel_task},
                                return_when=asyncio.FIRST_COMPLETED,
                            )
        if cancel_task in done:
            stream_task.cancel()
            try:
                await stream_task
            except asyncio.CancelledError:
                pass
            await cancel_task
            raise asyncio.CancelledError()
        cancel_task.cancel()
        await asyncio.gather(cancel_task, return_exceptions=True)

        try:
            yield stream_task.result()

        except StopAsyncIteration:
            return 

       


async def write_stream_event(
    run_id: str,
    event_type: str,
    payload: dict[str, Any],
    thread_id: str | None = None,
) -> str:
    """写入普通 Agent Run Stream 事件。"""

    return await write_agent_run_stream_event(
        run_id,
        event_type,
        payload,
        thread_id,
        ttl_seconds=RUN_REDIS_TTL_SECONDS,
    )


async def write_end_stream_event(
    run_id: str,
    payload: dict[str, Any],
    thread_id: str | None = None,
) -> str:
    """写入 Agent Run Stream 终态事件。"""

    return await write_stream_event(run_id, "end", payload, thread_id)


async def _finalize_run(
    run_id: str,
    *,
    status: str,
    thread_id: str,
    payload: dict[str, Any] | None = None,
    error: str | None = None,
    error_type: str | None = None,
) -> tuple[str, bool]:
    agent_status, changed = await set_run_terminal(
        run_id,
        status=status,
        error=error,
        error_type=error_type,
    )
    if agent_status is None:
        raise ValueError(f"Agent Run 不存在：{run_id}")

    end_payload = dict(payload or {})
    end_payload["status"] = agent_status
    if error is not None:
        end_payload["error"] = error

    try:
        if changed and agent_status:
            await write_end_stream_event(run_id, end_payload, thread_id)
    except Exception:
        if status != "failed":
            raise
        logger.exception(f"Agent run 错误事件发布失败：{run_id}")
    finally:
        if agent_status == "cancelled":
            await clear_agent_run_cancel_signal(run_id)

    return agent_status, changed


@dataclass
class StreamEventBucket:
    char_counts: int = 0
    chunks: list[dict[str, Any]] = field(default_factory=list)


def map_stream_event(chunk: dict[str, Any]) -> tuple[str, Any]:
    # 映射具体的类型
    status = chunk.get("status") or "some_event"
    if status == "loading":
        return "messages", chunk
    if status == "agent_state":
        return "custom", {
            "name": "agent_state",
            "chunk": chunk,
            "agent_state": chunk.get("response"),
        }
    if status == "finished":
        return "end", {"status": "completed", "chunk": chunk}

    raise ValueError(f"不支持的流事件状态：{status}")

class StreamEventSmoother:
    """按 thread_id 分桶保存连续的消息流事件。"""

    def __init__(
        self,
        *,
        run_id: str,
        character_limit: int,
    ) -> None:
        """初始化单个 Agent Run 的消息缓冲。"""

        if character_limit < 1:
            raise ValueError("character_limit 必须大于 0")

        self.run_id = run_id
        self.character_limit = character_limit
        self.chunk_buckets: dict[str | None, StreamEventBucket] = {}

    def calculate_character_count(self, chunk: dict[str, Any]):
        # tTODO 待实现char计数
        response = chunk.get("response")
        
        chunk_size = len(response) if isinstance(response, str) else 0
        stream_event = chunk.get("stream_event")
        if not isinstance(stream_event, dict):
            return chunk_size

        # 暂时不兼容v2
        return chunk_size


    async def append(
        self,
        chunk: dict[str, Any],
        thread_id: str | None = None,
    ) -> None:
        """把原始 chunk 保存到 thread_id 对应的 Bucket。"""

        bucket = self.chunk_buckets.setdefault(thread_id, StreamEventBucket())
        bucket.chunks.append(chunk)
        bucket.char_counts += self.calculate_character_count(chunk)

        # FIXME 需要重写counts
        if bucket.char_counts > self.character_limit:
            await self.release(thread_id)

    async def release(self, thread_id: str | None = None) -> None:
        """写入并清空指定 thread，未指定时释放当前 Run 的全部 Bucket。"""

        thread_ids = (
            tuple(self.chunk_buckets)
            if thread_id is None
            else (thread_id,)
        )
        for bucket_thread_id in thread_ids:
            bucket = self.chunk_buckets.get(bucket_thread_id)
            if bucket is None or not bucket.chunks:
                continue

            await write_stream_event(
                self.run_id,
                "messages",
                {"items": list(bucket.chunks)},
                bucket_thread_id,
            )
            bucket.chunks.clear()
            bucket.char_counts = 0

def _normalize_steam_agent_chunk(steam_agent_chunk_bytes: bytes) -> list[dict]:
    steam_agent_chunk_text = steam_agent_chunk_bytes.decode("utf-8")
    steam_agent_chunks: list[dict] = []
    for line in steam_agent_chunk_text.splitlines():
        line: str = line.strip()
        if not line:
            continue
        try:
            steam_agent_chunks.append(json.loads(line))
        except Exception:
            logger.warning(f"解析输出流失败{line}")
    return steam_agent_chunks


async def process_agent_run(ctx, run_id: str):
    agent_run_event: AgentRun | None = await _get_agent_run(run_id)
    if agent_run_event is None:
        logger.error(f"当前agent运行id：{run_id} 不存在")
        return

    # agent_status 是当前 Run 生命周期的唯一状态字段。
    initial_status = str(agent_run_event.agent_status)
    if initial_status in {"completed", "failed", "cancelled"}:
        return {"run_id": run_id, "status": initial_status}
    if initial_status == "cancel_requested":
        return await set_run_terminal(
            run_id,
            status="cancelled",
        )

    agent_input_message = await _get_agent_input_msg(
        message_id=agent_run_event.trigger_message_id  # ty:ignore[invalid-argument-type]
    )  # ty:ignore[invalid-argument-type]
    if agent_input_message is None:
        error = f"Input message not found: {agent_run_event.trigger_message_id}"
        logger.error(
            f"当前agent运行id：{run_id} 的输入消息不存在："
            f"{agent_run_event.trigger_message_id}"
        )
        return await _finalize_run(
            run_id,
            status="failed",
            thread_id=str(agent_run_event.thread_id),
            error=error,
            error_type="LookupError",
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
        msg_metadata=dict(agent_input_message.msg_metadata or {}),
    )

    # 配置整体metadata
    user = await _get_user(uid=uid)  # ty:ignore[invalid-argument-type]

    if not user:
        error = f"User not found: {uid}"
        return await _finalize_run(
            run_id,
            status="failed",
            thread_id=str(thread_id),
            error=error,
            error_type="LookupError",
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
        return await set_run_terminal(
            run_id,
            status="cancelled",
        )
    if running_status in {"completed", "failed", "cancelled"}:
        return {"run_id": run_id, "status": running_status}

    run_context = AgentRunContext(run_id)
    run_context.start()
    try:
        await write_stream_event(
            run_id,
            "status",
            {"status": "running"},
            str(thread_id),
        )
        terminal_payload: dict[str, Any] | None = None
        terminal_result: tuple[str, bool] | None = None
        stream_event_smoother = StreamEventSmoother(
            run_id=run_id,
            character_limit=20,
        )
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

                async for steam_agent_chunk in _cancellable_stream(
                    stream_thread_events,
                    run_context=run_context,
                ):
                    for strem_agent_chunk in _normalize_steam_agent_chunk(
                        steam_agent_chunk  # ty: ignore[invalid-argument-type]
                    ):  # ty: ignore[invalid-argument-type]
                        current_thread_id = reslove_thread_id(
                            strem_agent_chunk,
                            str(thread_id),
                        ) or str(thread_id)
                        logger.info(
                            "worker stream content | run_id=%s thread_id=%s chunk=%s",
                            run_id,
                            current_thread_id,
                            strem_agent_chunk,
                        )
                        if strem_agent_chunk.get("status") == "loading":
                            await stream_event_smoother.append(
                                strem_agent_chunk,
                                current_thread_id,
                            )
                            continue

                        await stream_event_smoother.release(
                            thread_id=current_thread_id
                        )

                        status = strem_agent_chunk.get("status") or "some_event"

                        event_type, payload = map_stream_event(strem_agent_chunk)

                        if event_type != "end":
                            await write_stream_event(
                                run_id,
                                event_type,
                                payload,
                                current_thread_id,
                            )

                        # 预防子agent和fathert,一般没啥问题
                        if current_thread_id != thread_id:
                            continue

                        if status == "finished":
                            terminal_result = await _finalize_run(
                                run_id=run_id,
                                status="completed",
                                thread_id=thread_id,  # ty: ignore[invalid-argument-type]
                                payload=strem_agent_chunk,
                            )
                            break

                    if terminal_result is not None:
                        break
            await stream_event_smoother.release()
            if terminal_result is not None:
                return terminal_result

            # 未正常结束则兜底
            if terminal_result is None:
                finish_payload = {
                    "status": "finished",
                    "request_id": request_id,
                }
                await _finalize_run(
                    run_id=run_id,
                    status="completed",
                    thread_id=thread_id,  # ty: ignore[invalid-argument-type]
                    payload=finish_payload,
                )
        except asyncio.CancelledError:
            logger.info(f"Agent run 收到取消请求：{run_id}")
            await stream_event_smoother.release()
            agent_status, changed = await set_run_terminal(
                run_id,
                status="cancelled",
            )
            if changed and agent_status:
                await write_end_stream_event(
                    run_id,
                    {"status": agent_status},
                    str(thread_id),
                )
            return agent_status, changed
        except Exception as exc:
            await _finalize_run(
                run_id,
                status="failed",
                thread_id=str(thread_id),
                error=str(exc),
                error_type=type(exc).__name__,
            )

            logger.exception(f"Agent run 执行失败：{run_id}")
            raise

        if await has_agent_run_cancel_signal(run_id):
            return await _finalize_run(
                run_id,
                status="cancelled",
                thread_id=str(thread_id),
            )

        return await _finalize_run(
            run_id,
            status="completed",
            thread_id=str(thread_id),
            payload=terminal_payload,
        )
    finally:
        await run_context.close()


class WorkerSettings:
    functions = [process_agent_run]
    queue_name = config.arq_queue_name
    redis_settings = RedisSettings.from_dsn(config.redis_url)
    max_jobs = config.arq_max_jobs
    on_startup = startup
    on_shutdown = shutdown
