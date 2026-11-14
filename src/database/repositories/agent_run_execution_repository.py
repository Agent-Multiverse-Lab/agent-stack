"""Agent Run 每次执行的租约与结束事实。

AgentRun 只保存业务聚合状态和当前 owner 快照；本 repository 拥有
`agent_run_execution` 的开放记录、心跳续租、过期查询和结束写入。每次 worker
认领 Run 都创建一条 execution，同一 Run 只允许一条开放 execution。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import AgentRunExecution


def as_utc(value: datetime) -> datetime:
    """把 SQLite 取出的 naive 时间按 UTC 处理，便于与 aware 时间比较。"""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class AgentRunExecutionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def open(
        self,
        run_id: str,
        *,
        worker_id: str | None = None,
        for_update: bool = False,
    ) -> AgentRunExecution | None:
        """读取 Run 当前开放的 execution；同一 Run 至多一条。"""

        statement = (
            select(AgentRunExecution)
            .where(
                AgentRunExecution.run_id == run_id,
                AgentRunExecution.finished_at.is_(None),
            )
            .order_by(AgentRunExecution.execution_no.desc())
            .limit(1)
        )
        if worker_id is not None:
            statement = statement.where(AgentRunExecution.worker_id == worker_id)
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def claim(
        self,
        run_id: str,
        *,
        worker_id: str,
        lease_seconds: float,
        now: datetime | None = None,
    ) -> AgentRunExecution:
        """在已锁定的 Run 内创建下一条 execution；调用方负责 Run 行锁。"""

        if not worker_id.strip():
            raise ValueError("worker_id 不能为空")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds 必须大于 0")

        current_time = now or datetime.now(UTC)
        max_execution_no = await self.session.scalar(
            select(func.coalesce(func.max(AgentRunExecution.execution_no), 0)).where(
                AgentRunExecution.run_id == run_id
            )
        )
        execution = AgentRunExecution(
            id=uuid4().hex,
            run_id=run_id,
            execution_no=int(max_execution_no or 0) + 1,
            worker_id=worker_id,
            status="running",
            started_at=current_time,
            heartbeat_at=current_time,
            lease_expires_at=current_time + timedelta(seconds=lease_seconds),
        )
        self.session.add(execution)
        await self.session.flush()
        return execution

    async def renew(
        self,
        execution_id: str,
        *,
        worker_id: str,
        lease_seconds: float,
        now: datetime | None = None,
    ) -> bool:
        """只续租仍由当前 worker 持有、尚未过期的开放 execution。"""

        if not worker_id.strip():
            raise ValueError("worker_id 不能为空")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds 必须大于 0")

        current_time = now or datetime.now(UTC)
        result = await self.session.execute(
            select(AgentRunExecution)
            .where(AgentRunExecution.id == execution_id)
            .with_for_update()
        )
        execution = result.scalar_one_or_none()
        if (
            execution is None
            or execution.finished_at is not None
            or execution.worker_id != worker_id
            or execution.lease_expires_at is None
        ):
            return False
        if as_utc(execution.lease_expires_at) <= as_utc(current_time):
            return False

        execution.heartbeat_at = current_time
        execution.lease_expires_at = current_time + timedelta(seconds=lease_seconds)
        await self.session.flush()
        return True

    async def close(
        self,
        execution: AgentRunExecution,
        *,
        status: str,
        error: str | None = None,
        error_type: str | None = None,
        now: datetime | None = None,
    ) -> AgentRunExecution:
        """写入 execution 的结束事实；已结束的 execution 不再改写。"""

        if execution.finished_at is None:
            execution.status = status
            execution.finished_at = now or datetime.now(UTC)
            execution.error = error
            execution.error_type = error_type
            await self.session.flush()
        return execution

    async def close_open(
        self,
        run_id: str,
        *,
        status: str,
        error: str | None = None,
        error_type: str | None = None,
        worker_id: str | None = None,
        now: datetime | None = None,
    ) -> list[AgentRunExecution]:
        """关闭 Run 的开放 execution；用于终态、重试和过期收敛。"""

        statement = select(AgentRunExecution).where(
            AgentRunExecution.run_id == run_id,
            AgentRunExecution.finished_at.is_(None),
        )
        if worker_id is not None:
            statement = statement.where(AgentRunExecution.worker_id == worker_id)
        result = await self.session.execute(statement.with_for_update())
        executions = list(result.scalars().all())
        for execution in executions:
            await self.close(
                execution,
                status=status,
                error=error,
                error_type=error_type,
                now=now,
            )
        return executions

    async def list_expired_run_ids(self, *, now: datetime | None = None) -> list[str]:
        """列出存在过期开放 execution 的 Run；不锁 execution，锁序由调用方统一。"""

        current_time = now or datetime.now(UTC)
        result = await self.session.execute(
            select(AgentRunExecution.run_id)
            .where(
                AgentRunExecution.finished_at.is_(None),
                AgentRunExecution.lease_expires_at.is_not(None),
                AgentRunExecution.lease_expires_at <= current_time,
            )
            .distinct()
        )
        return [str(run_id) for run_id in result.scalars().all()]

    async def list_open_run_ids(self) -> list[str]:
        """列出存在未结束开放 execution 的全部 Run。"""

        result = await self.session.execute(
            select(AgentRunExecution.run_id)
            .where(AgentRunExecution.finished_at.is_(None))
            .distinct()
        )
        return [str(run_id) for run_id in result.scalars().all()]
