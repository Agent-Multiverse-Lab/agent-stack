"""Model AIMessage 生命周期审计 Repository。

以当前 Run 的 lease 归属为边界，增量落库每次 Model 调用的顺序、状态、内容与
单次可靠 usage。
审计行使用 message_type=model_audit 与普通会话历史隔离，终态 State 对账时
（reconcile_to_history）才转为普通输出消息。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import MODEL_AUDIT_MESSAGE_TYPE, Message
from src.database.repositories.agent_run_repository import AgentRunRepository


class ModelMessageAuditRepository:
    """以当前 Run lease 为边界持久化 Model 生命周期。"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.run_repo = AgentRunRepository(db_session)

    async def start(
        self,
        *,
        run_id: str,
        request_id: str,
        thread_id: str,
        worker_id: str,
        operation_id: str,
        sequence: int,
        started_at: datetime,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[Message, bool]:
        """幂等创建 running 的 Model 审计消息，并返回是否首次创建。"""
        normalized_operation_id = operation_id.strip()
        if not normalized_operation_id:
            raise ValueError("Model operation_id 不能为空")
        if sequence < 0:
            raise ValueError("Model sequence 不能为负数")

        run = await self._lock_run(
            run_id=run_id,
            request_id=request_id,
            thread_id=thread_id,
            worker_id=worker_id,
        )
        existing = await self._get(run_id, normalized_operation_id)
        if existing is not None:
            self._require_same_owner(
                existing,
                conversation_id=int(run.conversation_id),
                request_id=request_id,
            )
            self._require_same_start(existing, sequence=sequence)
            return existing, False

        message = Message(
            conversation_id=int(run.conversation_id),
            agent_run_id=run.id,
            role="assistant",
            content="",
            message_type=MODEL_AUDIT_MESSAGE_TYPE,
            msg_metadata=dict(metadata or {}),
            request_id=request_id,
            status="completed",
            operation_id=normalized_operation_id,
            started_at=started_at,
            sequence=sequence,
            execution_status="running",
        )
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        return message, True

    async def finish(
        self,
        *,
        run_id: str,
        request_id: str,
        thread_id: str,
        worker_id: str,
        operation_id: str,
        content: str,
        finished_at: datetime,
        duration_ms: int | None,
        usage: dict[str, Any] | None,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        """完成同一 Model 审计消息；重复 finish 只接受相同业务结果。"""
        normalized_operation_id = operation_id.strip()
        if not normalized_operation_id:
            raise ValueError("Model operation_id 不能为空")
        if duration_ms is not None and duration_ms < 0:
            raise ValueError("Model duration_ms 不能为负数")

        run = await self._lock_run(
            run_id=run_id,
            request_id=request_id,
            thread_id=thread_id,
            worker_id=worker_id,
        )
        message = await self._get(run_id, normalized_operation_id)
        if message is None:
            raise ValueError("Model finish 缺少对应的 start 事实")
        self._require_same_owner(
            message,
            conversation_id=int(run.conversation_id),
            request_id=request_id,
        )

        normalized_usage = dict(usage) if isinstance(usage, dict) else None
        if message.execution_status == "completed":
            if message.content != content or message.usage != normalized_usage:
                raise ValueError("已完成 Model 审计事实不能被不同结果覆盖")
            return message
        if message.execution_status != "running":
            raise ValueError(
                f"Model 审计事实不能从 {message.execution_status} 转为 completed"
            )

        message.content = content
        message.finished_at = finished_at
        message.duration_ms = duration_ms
        message.execution_status = "completed"
        message.usage = normalized_usage
        message.msg_metadata = {**dict(message.msg_metadata or {}), **dict(metadata or {})}
        await self.db.flush()
        await self.db.refresh(message)
        return message

    async def reconcile_to_history(
        self,
        *,
        run_id: str,
        operation_id: str,
        content: str,
        message_metadata: dict[str, Any] | None = None,
        finished_at: datetime | None = None,
    ) -> Message | None:
        """把终态 State 能按 operation_id 证明的审计行转为普通输出。

        复用增量事实里已经保存的 started_at / sequence / duration_ms，不覆盖
        进程内已经观察到的生命周期事实。
        """
        message = await self._get(run_id, operation_id)
        if message is None:
            return None

        message.content = content
        message.message_type = "text"
        message.execution_status = "completed"
        message.finished_at = message.finished_at or finished_at or datetime.now(UTC)
        message.msg_metadata = {**dict(message.msg_metadata or {}), **dict(message_metadata or {})}
        await self.db.flush()
        await self.db.refresh(message)
        return message

    async def get(self, *, run_id: str, operation_id: str) -> Message | None:
        """按同一 Run 的稳定来源键读取审计消息。"""
        return await self._get(run_id, operation_id)

    async def list_for_run(self, run_id: str) -> list[Message]:
        """按 ProtocolEvent sequence 返回 Run 的 Model 时间线。"""
        result = await self.db.execute(
            select(Message)
            .where(
                Message.agent_run_id == run_id,
                Message.operation_id.is_not(None),
                Message.role == "assistant",
            )
            .order_by(Message.sequence.asc(), Message.id.asc())
        )
        return list(result.scalars().all())

    async def _get(self, run_id: str, operation_id: str) -> Message | None:
        result = await self.db.execute(
            select(Message)
            .where(
                Message.agent_run_id == run_id,
                Message.operation_id == operation_id,
                Message.role == "assistant",
            )
            .order_by(Message.id.asc())
            .execution_options(populate_existing=True)
        )
        return result.scalars().first()

    async def _lock_run(
        self,
        *,
        run_id: str,
        request_id: str,
        thread_id: str,
        worker_id: str,
    ):
        run = await self.run_repo.lock_output_persistence(
            run_id,
            worker_id=worker_id,
            conversation_thread_id=thread_id,
            request_id=request_id,
        )
        if run is None:
            raise ValueError(f"AgentRun 不存在: {run_id}")
        return run

    @staticmethod
    def _require_same_owner(
        message: Message,
        *,
        conversation_id: int,
        request_id: str,
    ) -> None:
        if (
            int(message.conversation_id) != conversation_id
            or message.request_id != request_id
            or message.role != "assistant"
        ):
            raise ValueError("Model 审计消息必须属于同一 Run、request 和 conversation")

    @staticmethod
    def _require_same_start(message: Message, *, sequence: int) -> None:
        """确保重放的 Model start 没有改写已持久化顺序。"""
        if message.sequence != sequence:
            raise ValueError("重复 Model start 与已持久化 sequence 不一致")
