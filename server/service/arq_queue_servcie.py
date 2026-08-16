from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from redis.asyncio.client import PubSub

from src.configs import config
from src.storage import create_arq_pool, get_async_redis_client
from src.utils import logger

_arq_pool = None
RUN_REDIS_TTL_SECONDS = 24 * 60 * 60
AGENT_RUN_CANCEL_CHANNEL = "run:cancel"


async def get_arq_pool():
    global _arq_pool
    if _arq_pool is None:
        _arq_pool = await create_arq_pool()
    return _arq_pool


@asynccontextmanager
async def subscribe_redis_channel(channel: str) -> AsyncIterator[PubSub]:
    """订阅信道，并在退出上下文时关闭 PubSub。"""

    redis = await get_async_redis_client()
    pubsub = redis.pubsub()
    try:
        await pubsub.subscribe(channel)
    except Exception:
        await pubsub.aclose()
        raise

    try:
        yield pubsub
    finally:
        await pubsub.aclose()


def queue_event_stream_key(run_id: str) -> str:
    return f"run:events:{run_id}"


def agent_run_cancel_key(run_id: str) -> str:
    return f"run:cancel:{run_id}"


def build_agent_chunk_envolope(
    *,
    run_id: str,
    event_type: str,
    thread_id: str | None = None,
    payload: dict | None = None,
    created_at: str | None = None,
):
    return {
        "run_id": run_id,
        "event_type": event_type,
        "thread_id": thread_id,
        "payload": payload,
        "created_at": created_at,
    }


async def write_agent_run_stream_event(
    run_id: str,
    event_type: str,
    event: dict[str, Any],
    thread_id: str | None = None,
    *,
    ttl_seconds: int | None = None,
) -> str:
    """将完整的 Agent Run 事件写入 Redis Stream。"""

    redis_client = await get_async_redis_client()
    stream_key = queue_event_stream_key(run_id)

    chunk_envelope = build_agent_chunk_envolope(
        run_id=run_id,
        event_type=event_type,
        thread_id=thread_id,
        payload=event,
        created_at=datetime.now(tz=UTC).isoformat(),
    )

    fields = {
        "event_type": event_type,
        "event": json.dumps(chunk_envelope, ensure_ascii=False, default=str),
    }

    event_id = await redis_client.xadd(
        stream_key,
        fields=fields,
        maxlen=config.run_stream_max_len,
        approximate=True,
    )
    if ttl_seconds is not None:
        await redis_client.expire(stream_key, ttl_seconds)

    return event_id.decode() if isinstance(event_id, bytes) else str(event_id)


async def read_agent_run_stream_events(
    run_id: str,
    *,
    after_id: str = "0-0",
    count: int | None = None,
    block_ms: int | None = None,
):
    redis = await get_async_redis_client()
    return await redis.xread(
        streams={queue_event_stream_key(run_id): after_id},
        count=count,
        block=config.run_stream_poll_timeout_ms if block_ms is None else block_ms,
    )


async def read_recent_agent_run_stream_events(
    run_id: str,
    *,
    count: int,
):
    """只读取 Agent Run Stream 最近 N 条事件。"""

    redis = await get_async_redis_client()
    return await redis.xrevrange(
        queue_event_stream_key(run_id),
        max="+",
        min="-",
        count=count,
    )


async def publish_agent_run_cancel_signal(
    run_id: str,
    *,
    reason: str | None = None,
) -> None:
    """持久化 Agent Run 取消信号并通过 Pub/Sub 唤醒 Worker。"""

    try:
        redis = await get_async_redis_client()
        payload = {
            "run_id": run_id,
            "status": "cancel_requested",
            "reason": reason or "cancel_requested",
            "created_at": datetime.now(UTC).isoformat(),
        }
        await redis.set(
            agent_run_cancel_key(run_id),
            json.dumps(payload, ensure_ascii=False),
            ex=RUN_REDIS_TTL_SECONDS,
        )
        await redis.publish(AGENT_RUN_CANCEL_CHANNEL, run_id)
    except Exception:
        logger.exception(f"Agent Run 取消信号发布失败：{run_id}")
        raise


async def wait_agent_run_cancel_signal(run_id: str) -> bool:
    """等待指定 Agent Run 的持久化取消信号或 Pub/Sub 消息。"""

    try:
        if await has_agent_run_cancel_signal(run_id):
            return True

        async with subscribe_redis_channel(AGENT_RUN_CANCEL_CHANNEL) as pubsub:
            while True:
                message = await pubsub.get_message(timeout=None)
                if message is None:
                    continue

                if message.get("type") == "subscribe":
                    # 每次订阅确认后重查 key，同时覆盖首次订阅竞态和断线重订阅。
                    if await has_agent_run_cancel_signal(run_id):
                        return True
                    continue

                message_run_id = message.get("data")
                if isinstance(message_run_id, bytes):
                    message_run_id = message_run_id.decode()
                if message_run_id == run_id:
                    return True
    except Exception:
        logger.exception(f"Agent Run 取消信号监听失败：{run_id}")
        raise


async def has_agent_run_cancel_signal(run_id: str) -> bool:
    """检查 Agent Run 的 Redis 取消信号是否存在。"""

    redis = await get_async_redis_client()
    return bool(await redis.exists(agent_run_cancel_key(run_id)))


async def clear_agent_run_cancel_signal(run_id: str) -> None:
    """清理已由 Worker 消费的 Agent Run 取消信号。"""

    redis = await get_async_redis_client()
    await redis.delete(agent_run_cancel_key(run_id))
