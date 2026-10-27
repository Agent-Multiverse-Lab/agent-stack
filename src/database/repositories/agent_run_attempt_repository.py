"""Agent Run 执行尝试的租约与结束事实。

AgentRun 只保存业务聚合状态和当前 owner 快照；本 repository 拥有
`agent_run_attempt` 的开放尝试、心跳续租、过期查询和结束写入。每次 worker
认领 Run 都创建一条 attempt，同一 Run 只允许一条开放 attempt。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import AgentRunAttempt


def as_utc(value: datetime) -> datetime:
    """把 SQLite 取出的 naive 时间按 UTC 处理，便于与 aware 时间比较。"""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class AgentRunAttemptRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def open(
        self,
        run_id: str,
        *,
        worker_id: str | None = None,
        for_update: bool = False,
    ) -> AgentRunAttempt | None:
        """读取 Run 当前开放的 attempt；同一 Run 至多一条。"""

        statement = (
            select(AgentRunAttempt)
            .where(
                AgentRunAttempt.run_id == run_id,
                AgentRunAttempt.finished_at.is_(None),
            )
            .order_by(AgentRunAttempt.attempt_no.desc())
            .limit(1)
        )
        if worker_id is not None:
            statement = statement.where(AgentRunAttempt.worker_id == worker_id)
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
    ) -> AgentRunAttempt:
        """在已锁定的 Run 内创建下一条 attempt；调用方负责 Run 行锁。"""

        if not worker_id.strip():
            raise ValueError("worker_id 不能为空")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds 必须大于 0")

        current_time = now or datetime.now(UTC)
        max_attempt_no = await self.session.scalar(
            select(func.coalesce(func.max(AgentRunAttempt.attempt_no), 0)).where(
                AgentRunAttempt.run_id == run_id
            )
        )
        attempt = AgentRunAttempt(
            id=uuid4().hex,
            run_id=run_id,
            attempt_no=int(max_attempt_no or 0) + 1,
            worker_id=worker_id,
            status="running",
            started_at=current_time,
            heartbeat_at=current_time,
            lease_expires_at=current_time + timedelta(seconds=lease_seconds),
        )
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def renew(
        self,
        attempt_id: str,
        *,
        worker_id: str,
        lease_seconds: float,
        now: datetime | None = None,
    ) -> bool:
        """只续租仍由当前 worker 持有、尚未过期的开放 attempt。"""

        if not worker_id.strip():
            raise ValueError("worker_id 不能为空")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds 必须大于 0")

        current_time = now or datetime.now(UTC)
        result = await self.session.execute(
            select(AgentRunAttempt)
            .where(AgentRunAttempt.id == attempt_id)
            .with_for_update()
        )
        attempt = result.scalar_one_or_none()
        if (
            attempt is None
            or attempt.finished_at is not None
            or attempt.worker_id != worker_id
            or attempt.lease_expires_at is None
        ):
            return False
        if as_utc(attempt.lease_expires_at) <= as_utc(current_time):
            return False

        attempt.heartbeat_at = current_time
        attempt.lease_expires_at = current_time + timedelta(seconds=lease_seconds)
        await self.session.flush()
        return True

    async def close(
        self,
        attempt: AgentRunAttempt,
        *,
        status: str,
        error: str | None = None,
        error_type: str | None = None,
        now: datetime | None = None,
    ) -> AgentRunAttempt:
        """写入 attempt 的结束事实；已结束的 attempt 不再改写。"""

        if attempt.finished_at is None:
            attempt.status = status
            attempt.finished_at = now or datetime.now(UTC)
            attempt.error = error
            attempt.error_type = error_type
            await self.session.flush()
        return attempt

    async def close_open(
        self,
        run_id: str,
        *,
        status: str,
        error: str | None = None,
        error_type: str | None = None,
        worker_id: str | None = None,
        now: datetime | None = None,
    ) -> list[AgentRunAttempt]:
        """关闭 Run 的开放 attempt；用于终态、重试和过期收敛。"""

        statement = select(AgentRunAttempt).where(
            AgentRunAttempt.run_id == run_id,
            AgentRunAttempt.finished_at.is_(None),
        )
        if worker_id is not None:
            statement = statement.where(AgentRunAttempt.worker_id == worker_id)
        result = await self.session.execute(statement.with_for_update())
        attempts = list(result.scalars().all())
        for attempt in attempts:
            await self.close(
                attempt,
                status=status,
                error=error,
                error_type=error_type,
                now=now,
            )
        return attempts

    async def list_expired_run_ids(self, *, now: datetime | None = None) -> list[str]:
        """列出存在过期开放 attempt 的 Run；不锁 attempt，锁序由调用方统一。"""

        current_time = now or datetime.now(UTC)
        result = await self.session.execute(
            select(AgentRunAttempt.run_id)
            .where(
                AgentRunAttempt.finished_at.is_(None),
                AgentRunAttempt.lease_expires_at.is_not(None),
                AgentRunAttempt.lease_expires_at <= current_time,
            )
            .distinct()
        )
        return [str(run_id) for run_id in result.scalars().all()]
