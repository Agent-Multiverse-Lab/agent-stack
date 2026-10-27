import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.database.models import AUDIT_MESSAGE_TYPES, AgentRun, Conversation, Message

from .agent_run_attempt_repository import AgentRunAttemptRepository

AGENT_RUN_TERMINAL_STATUSES = frozenset(
    {"completed", "failed", "cancelled", "interrupted"}
)
# 持有租约、需要 reaper 关注的 Run 状态。
AGENT_RUN_LEASED_STATUSES = frozenset({"running", "cancel_requested"})
# 只有正常执行阶段需要周期性续租；cancel_requested 停止续租，保留最后一次
# 租约用于取消收尾，超时交给 reaper 收敛。
AGENT_RUN_RENEWABLE_STATUSES = frozenset({"running"})
# 默认租约 120 秒；Worker 每 30 秒续期一次，过期即视为执行者失联。
DEFAULT_RUN_LEASE_SECONDS = 120.0


@dataclass(frozen=True)
class RunStopState:
    """当前 worker 持有的 Run 是否应停止执行。

    `reason` 是稳定分类：not_found/terminal/cancel_requested/attempt_missing/
    owner_mismatch/lease_expired。controller 只把非取消类原因视为 lease 丢失。
    """

    stopped: bool
    reason: str | None = None
    attempt_id: str | None = None


def _as_utc(value: datetime) -> datetime:
    """把 SQLite 取出的 naive 时间按 UTC 处理，便于与 aware 时间比较。"""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _audit_terminal_status(run_status: str) -> str:
    """把 Agent Run 终态映射为残留审计行的收敛终态。"""
    if run_status == "failed":
        return "failed"
    if run_status in {"cancelled", "interrupted"}:
        return "interrupted"
    return "abandoned"


class AgentRunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.attempts = AgentRunAttemptRepository(session)

    async def get_by_id(self, run_id: str) -> AgentRun | None:
        result = await self.session.execute(
            select(AgentRun)
            .where(AgentRun.id == run_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def set_output_message(
        self,
        *,
        run_id: str,
        output_message_id: int,
        worker_id: str,
    ) -> AgentRun:
        """记录当前 Run 最新保存的输出 Message。"""
        run = await self.lock_for_output_update(run_id, worker_id=worker_id)
        run.output_message_id = output_message_id
        await self.session.flush()
        return run

    async def get_child_for_parent(
        self,
        *,
        run_id: str,
        parent_run_id: str,
    ) -> AgentRun | None:
        """按父运行作用域查询子运行，并校验父子用户归属一致。"""

        parent_run = aliased(AgentRun)
        result = await self.session.execute(
            select(AgentRun)
            .join(parent_run, parent_run.id == AgentRun.parent_run_id)
            .where(
                AgentRun.id == run_id,
                parent_run.id == parent_run_id,
                AgentRun.uid == parent_run.uid,
                AgentRun.run_type == "subagent",
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list_active_child_runs(
        self,
        *,
        parent_run_id: str,
        uid: str,
    ) -> list[AgentRun]:
        """列出当前用户指定主 Run 下尚未结束的直接子 Agent Run。"""

        result = await self.session.execute(
            select(AgentRun)
            .join(Conversation, Conversation.id == AgentRun.conversation_id)
            .where(
                AgentRun.parent_run_id == parent_run_id,
                AgentRun.uid == uid,
                Conversation.uid == uid,
                AgentRun.run_type == "subagent",
                AgentRun.agent_status.not_in(AGENT_RUN_TERMINAL_STATUSES),
                Conversation.deleted_at.is_(None),
            )
            .execution_options(populate_existing=True)
        )
        return list(result.scalars().all())

    async def create_run(
        self,
        *,
        run_id: str,
        thread_id: str,
        conversation_id: int | str,
        uid: str,
        agent_slug: str,
        request_id: str,
        trigger_message_id: int | None,
        agent_status: str = "pending",
        run_type: str = "chat",
        parent_run_id: str | None = None,
        run_metadata: dict | None = None,
    ) -> AgentRun:
        """创建持久化 Agent Run。"""
        run = AgentRun(
            id=run_id,
            thread_id=thread_id,
            conversation_id=int(conversation_id),
            uid=uid,
            agent_id=agent_slug,
            request_id=request_id,
            trigger_message_id=trigger_message_id,
            run_type=run_type,
            agent_status=agent_status,
            parent_run_id=parent_run_id,
            run_metadata=dict(run_metadata or {}),
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_by_id_for_user(
        self,
        *,
        run_id: str,
        uid: str,
    ) -> AgentRun | None:
        """按运行 ID 和用户归属查询 Agent Run。"""

        result = await self.session.execute(
            select(AgentRun)
            .join(Conversation, Conversation.id == AgentRun.conversation_id)
            .where(
                AgentRun.id == run_id,
                AgentRun.uid == uid,
                Conversation.uid == uid,
                Conversation.deleted_at.is_(None),
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_user_and_thread(
        self,
        *,
        run_id: str,
        uid: str,
        thread_id: str,
    ) -> AgentRun | None:
        """查询属于当前用户和会话的 Agent Run。"""
        result = await self.session.execute(
            select(AgentRun)
            .join(Conversation, Conversation.id == AgentRun.conversation_id)
            .where(
                AgentRun.id == run_id,
                AgentRun.uid == uid,
                AgentRun.thread_id == thread_id,
                Conversation.uid == uid,
                Conversation.thread_id == thread_id,
                Conversation.deleted_at.is_(None),
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_by_ids_for_conversation(
        self,
        *,
        run_ids: Sequence[str],
        conversation_id: int,
    ) -> dict[str, AgentRun]:
        """批量读取一页消息在当前对话中关联的 Agent Run。"""
        if not run_ids:
            return {}

        result = await self.session.execute(
            select(AgentRun).where(
                AgentRun.id.in_(run_ids),
                AgentRun.conversation_id == conversation_id,
            )
        )
        runs = result.scalars().all()
        return {str(run.id): run for run in runs}

    async def has_active_for_conversations(
        self,
        *,
        conversation_ids: Sequence[int],
        uid: str,
    ) -> bool:
        """判断当前用户的一组对话是否仍有未终止的 Run。"""
        if not conversation_ids:
            return False

        result = await self.session.execute(
            select(AgentRun.id)
            .where(
                AgentRun.conversation_id.in_(conversation_ids),
                AgentRun.uid == uid,
                AgentRun.agent_status.not_in(AGENT_RUN_TERMINAL_STATUSES),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _lock_update(self, run_id: str) -> AgentRun | None:
        result = await self.session.execute(
            select(AgentRun)
            .where(AgentRun.id == run_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_open_attempt(
        self,
        run_id: str,
        *,
        worker_id: str | None = None,
        for_update: bool = False,
    ):
        """读取 Run 当前开放的 attempt；供 worker/管理路径复用。"""
        return await self.attempts.open(
            run_id,
            worker_id=worker_id,
            for_update=for_update,
        )

    async def check_run_stopped(
        self,
        run_id: str,
        *,
        worker_id: str,
        now: datetime | None = None,
    ) -> RunStopState:
        """判断当前 worker 持有的 Run 是否已经停止或失去执行权。

        判定顺序：Run 不存在/终态 -> 没有开放 attempt -> owner 不一致 ->
        attempt 租约过期 -> 用户已请求取消。`cancel_requested` 不是终态，但
        worker 必须停止；调用方据此区分取消和 lease 丢失。
        """

        if not worker_id.strip():
            raise ValueError("worker_id 不能为空")
        current_time = now or datetime.now(UTC)
        run = await self.get_by_id(run_id)
        if run is None:
            return RunStopState(True, "not_found")
        if str(run.agent_status) in AGENT_RUN_TERMINAL_STATUSES:
            return RunStopState(True, "terminal")
        attempt = await self.attempts.open(run_id)
        if attempt is None:
            return RunStopState(True, "attempt_missing")
        if run.worker_id != worker_id or attempt.worker_id != worker_id:
            return RunStopState(True, "owner_mismatch", attempt.id)
        if attempt.lease_expires_at is None or _as_utc(attempt.lease_expires_at) <= _as_utc(current_time):
            return RunStopState(True, "lease_expired", attempt.id)
        if str(run.agent_status) == "cancel_requested":
            return RunStopState(True, "cancel_requested", attempt.id)
        return RunStopState(False, None, attempt.id)

    async def is_run_stopped(
        self,
        run_id: str,
        *,
        worker_id: str,
        now: datetime | None = None,
    ) -> bool:
        """`check_run_stopped` 的布尔便捷入口。"""
        return (await self.check_run_stopped(run_id, worker_id=worker_id, now=now)).stopped

    async def lock_for_output_update(
        self, run_id: str, *, worker_id: str
    ) -> AgentRun:
        """在消息事务内锁定 Run，只允许仍持有效 attempt 租约的 owner 保存输出。"""
        run = await self._lock_update(run_id)
        if run is None:
            raise LookupError(f"Agent Run 不存在：{run_id}")
        if run.worker_id != worker_id or str(run.agent_status) not in {
            "running", "cancel_requested"
        }:
            raise RuntimeError(f"Agent Run 当前执行归属不匹配：{run_id}")
        attempt = await self.attempts.open(run_id, worker_id=worker_id, for_update=True)
        if attempt is not None:
            if (
                attempt.lease_expires_at is None
                or _as_utc(attempt.lease_expires_at) <= _as_utc(datetime.now(UTC))
            ):
                raise RuntimeError(f"Agent Run 当前执行租约已过期：{run_id}")
        else:
            # 兼容迁移前已认领的 Run：新认领一定会创建 attempt，旧 Run 只校验
            # Run 级租约，避免滚动升级窗口内误伤正在收尾的执行。
            lease = getattr(run, "lease_expires_at", None)
            if lease is not None and _as_utc(lease) <= _as_utc(datetime.now(UTC)):
                raise RuntimeError(f"Agent Run 当前执行租约已过期：{run_id}")
        return run

    async def lock_output_persistence(
        self,
        run_id: str,
        *,
        worker_id: str,
        conversation_thread_id: str,
        request_id: str,
    ) -> AgentRun | None:
        """在审计写入前锁定并校验当前 attempt 的完整因果边界。

        输出持久化前必须确认：Run 仍由当前 attempt 的 owner 持有、attempt
        租约未过期，且 thread/request 与本 Run 的归属一致。
        """
        if not worker_id.strip():
            raise ValueError("worker_id 不能为空")
        run = await self._lock_update(run_id)
        if run is None:
            return None
        if run.worker_id != worker_id or str(run.agent_status) not in {
            "running",
            "cancel_requested",
        }:
            raise RuntimeError(f"Agent Run 当前执行归属不匹配：{run_id}")
        attempt = await self.attempts.open(run_id, worker_id=worker_id, for_update=True)
        if attempt is not None:
            if (
                attempt.lease_expires_at is None
                or _as_utc(attempt.lease_expires_at) <= _as_utc(datetime.now(UTC))
            ):
                raise RuntimeError(f"Agent Run 当前执行租约已过期：{run_id}")
        else:
            lease = getattr(run, "lease_expires_at", None)
            if lease is not None and _as_utc(lease) <= _as_utc(datetime.now(UTC)):
                raise RuntimeError(f"Agent Run 当前执行租约已过期：{run_id}")
        if run.thread_id != conversation_thread_id or run.request_id != request_id:
            raise ValueError("AgentRun 输出必须属于同一 thread 和 request")
        if run.conversation_id is None:
            raise ValueError("AgentRun 输出缺少 conversation 归属")
        return run

    async def close_running_audit_messages(
        self, run_id: str, *, execution_status: str
    ) -> int:
        """按 Run 终态收敛残留的 running 审计消息。

        终态映射：failed 映射 failed，取消/中断映射 interrupted，成功终态仍未
        得到 finish 证明的行映射 abandoned。
        """
        if execution_status not in {"failed", "interrupted", "abandoned"}:
            raise ValueError(f"不支持的审计终态：{execution_status}")
        result = await self.session.execute(
            update(Message)
            .where(
                Message.agent_run_id == run_id,
                Message.execution_status == "running",
                Message.message_type.in_(AUDIT_MESSAGE_TYPES),
            )
            .values(
                execution_status=execution_status,
                # 保留已观察到的结束时间（如 tool-error），只补全缺失的。
                finished_at=func.coalesce(Message.finished_at, datetime.now(UTC)),
            )
        )
        return int(result.rowcount or 0)

    # FIXEME: 锁定父 Run 后，Resume 创建与重复请求判断必须处于同一事务。
    async def get_for_resume_for_update(
        self,
        *,
        run_id: str,
        uid: str,
        thread_id: str,
    ) -> AgentRun | None:
        result = await self.session.execute(
            select(AgentRun)
            .join(Conversation, Conversation.id == AgentRun.conversation_id)
            .where(
                AgentRun.id == run_id,
                AgentRun.uid == uid,
                AgentRun.thread_id == thread_id,
                Conversation.uid == uid,
                Conversation.thread_id == thread_id,
                Conversation.deleted_at.is_(None),
            )
            .with_for_update(of=AgentRun)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    # FIXEME: Resume 与 SubAgent 共用 parent_run_id，查询必须显式限制 run_type。
    async def get_resume_child(self, parent_run_id: str) -> AgentRun | None:
        result = await self.session.execute(
            select(AgentRun)
            .where(
                AgentRun.parent_run_id == parent_run_id,
                AgentRun.run_type == "resume",
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    # FIXEME: Thread 刷新时直接返回尚在执行的最新 Run，Resume 不依赖消息关联。
    async def get_latest_active_for_thread(
        self,
        *,
        uid: str,
        thread_id: str,
    ) -> AgentRun | None:
        result = await self.session.execute(
            select(AgentRun)
            .join(Conversation, Conversation.id == AgentRun.conversation_id)
            .where(
                AgentRun.uid == uid,
                AgentRun.thread_id == thread_id,
                AgentRun.agent_status.not_in(AGENT_RUN_TERMINAL_STATUSES),
                Conversation.uid == uid,
                Conversation.thread_id == thread_id,
                Conversation.deleted_at.is_(None),
            )
            .order_by(AgentRun.created_at.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    # FIXEME: 只有尚无 Resume 子 Run 的最新 interrupted Run 仍待用户回答。
    async def get_pending_interaction_run(
        self,
        *,
        uid: str,
        thread_id: str,
    ) -> AgentRun | None:
        resume_child = aliased(AgentRun)
        result = await self.session.execute(
            select(AgentRun)
            .join(Conversation, Conversation.id == AgentRun.conversation_id)
            .outerjoin(
                resume_child,
                (resume_child.parent_run_id == AgentRun.id)
                & (resume_child.run_type == "resume"),
            )
            .where(
                AgentRun.uid == uid,
                AgentRun.thread_id == thread_id,
                AgentRun.agent_status == "interrupted",
                Conversation.uid == uid,
                Conversation.thread_id == thread_id,
                Conversation.deleted_at.is_(None),
                resume_child.id.is_(None),
            )
            .order_by(AgentRun.created_at.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def set_running(
        self,
        run_id: str,
        *,
        worker_id: str,
        lease_seconds: float = DEFAULT_RUN_LEASE_SECONDS,
        now: datetime | None = None,
    ) -> AgentRun | None:
        """在行锁内认领 Run，并为本次执行创建 attempt。

        认领在 AgentRun 上留下当前 owner 快照，真正的执行权、心跳和租约写入
        `agent_run_attempt`；Worker 执行期间必须周期性调用 `renew_lease`。
        """

        if not worker_id.strip():
            raise ValueError("worker_id 不能为空")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds 必须大于 0")

        current_time = now or datetime.now(UTC)
        run = await self._lock_update(run_id)
        if run is None:
            return None
        current_status = str(run.agent_status)
        if current_status in AGENT_RUN_TERMINAL_STATUSES:
            return run
        if run.worker_id is not None or current_status not in {
            "pending", "queued", "cancel_requested"
        }:
            return None

        # 正常路径不应存在开放 attempt；若存在，说明上次执行没有正常收口，
        # 先以 lease_expired 结束它，再创建新 attempt。
        stale = await self.attempts.open(run_id, for_update=True)
        if stale is not None:
            await self.attempts.close(
                stale,
                status="lease_expired",
                error="Attempt was still open when a new owner claimed the run",
                error_type="LeaseExpired",
                now=current_time,
            )

        attempt = await self.attempts.claim(
            run_id,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
            now=current_time,
        )
        run.worker_id = worker_id
        if current_status != "cancel_requested":
            run.agent_status = "running"
        run.started_at = run.started_at or current_time
        run.heartbeat_at = attempt.heartbeat_at
        run.lease_expires_at = attempt.lease_expires_at
        run.error = None
        run.error_type = None
        await self.session.flush()
        return run

    async def renew_lease(
        self,
        run_id: str,
        *,
        worker_id: str,
        lease_seconds: float = DEFAULT_RUN_LEASE_SECONDS,
        now: datetime | None = None,
    ) -> bool:
        """续租当前开放 attempt；AgentRun 上的时间只做查询快照镜像。

        续租以 attempt 的 owner 和到期时间为准；Run 级心跳/到期时间同步更新，
        便于现有查询与过期扫描使用。attempt 不存在或不是当前 owner 时返回
        False，调用方必须停止执行。
        """

        if not worker_id.strip():
            raise ValueError("worker_id 不能为空")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds 必须大于 0")

        current_time = now or datetime.now(UTC)
        run = await self._lock_update(run_id)
        if (
            run is None
            or str(run.agent_status) not in AGENT_RUN_RENEWABLE_STATUSES
            or run.worker_id != worker_id
            or run.lease_expires_at is None
        ):
            return False
        if _as_utc(run.lease_expires_at) <= _as_utc(current_time):
            return False

        attempt = await self.attempts.open(run_id, worker_id=worker_id, for_update=True)
        if attempt is None:
            return False
        if not await self.attempts.renew(
            attempt.id,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
            now=current_time,
        ):
            return False
        run.heartbeat_at = attempt.heartbeat_at
        run.lease_expires_at = attempt.lease_expires_at
        await self.session.flush()
        return True

    async def reconcile_expired_leases(
        self, *, now: datetime | None = None
    ) -> list[AgentRun]:
        """把租约过期的开放 attempt / Run 收敛为失败或取消终态。

        候选来自两处：attempt 租约过期，以及迁移前没有 attempt 但 Run 级租约
        过期的旧 Run。每个 Run 在行锁内处理，先关 attempt 再落 Run 终态，并在
        同一事务内收敛残留的 running 审计行。
        """

        current_time = now or datetime.now(UTC)
        candidate_ids = set(await self.attempts.list_expired_run_ids(now=current_time))
        legacy = await self.session.execute(
            select(AgentRun.id).where(
                AgentRun.agent_status.in_(tuple(AGENT_RUN_LEASED_STATUSES)),
                AgentRun.worker_id.is_not(None),
                AgentRun.lease_expires_at.is_not(None),
                AgentRun.lease_expires_at <= current_time,
            )
        )
        candidate_ids.update(str(run_id) for run_id in legacy.scalars().all())

        runs: list[AgentRun] = []
        for run_id in sorted(candidate_ids):
            run = await self._lock_update(run_id)
            if run is None:
                continue
            current_status = str(run.agent_status)
            if current_status in AGENT_RUN_TERMINAL_STATUSES:
                await self.attempts.close_open(
                    run_id,
                    status="orphaned",
                    error="Run was already terminal while its attempt was open",
                    error_type="OrphanedAttempt",
                    now=current_time,
                )
                continue

            # 候选是锁外查询得到的；锁到 Run 后复查 attempt/lease，避免把
            # 刚续租成功的执行误判为过期。
            open_attempt = await self.attempts.open(run_id)
            if (
                open_attempt is not None
                and open_attempt.lease_expires_at is not None
                and _as_utc(open_attempt.lease_expires_at) > _as_utc(current_time)
            ):
                continue
            if (
                open_attempt is None
                and run.lease_expires_at is not None
                and _as_utc(run.lease_expires_at) > _as_utc(current_time)
            ):
                continue

            cancelled = current_status == "cancel_requested"
            await self.attempts.close_open(
                run_id,
                status="cancelled" if cancelled else "lease_expired",
                error=None if cancelled else "Worker lease expired before the run finished",
                error_type=None if cancelled else "LeaseExpired",
                now=current_time,
            )
            run.agent_status = "cancelled" if cancelled else "failed"
            run.finished_at = current_time
            run.worker_id = None
            run.heartbeat_at = None
            run.lease_expires_at = None
            if not cancelled:
                run.error = "Worker lease expired before the run finished"
                run.error_type = "LeaseExpired"
            await self.close_running_audit_messages(
                run_id,
                execution_status=_audit_terminal_status(str(run.agent_status)),
            )
            runs.append(run)

        if runs:
            await self.session.flush()
        return runs

    async def release_for_retry(self, run_id: str, *, worker_id: str) -> bool:
        """仅当前 attempt 可以释放归属，供 ARQ 下一次重试重新领取。"""

        run = await self._lock_update(run_id)
        if run is None or run.worker_id != worker_id:
            return False
        if str(run.agent_status) not in {"running", "cancel_requested"}:
            return False

        current_time = datetime.now(UTC)
        attempt = await self.attempts.open(run_id, worker_id=worker_id, for_update=True)
        if attempt is not None:
            await self.attempts.close(
                attempt,
                status="retry_released",
                now=current_time,
            )
        if str(run.agent_status) == "running":
            run.agent_status = "pending"
        run.worker_id = None
        run.heartbeat_at = None
        run.lease_expires_at = None
        await self.session.flush()
        return True

    async def set_agent_terminal(
        self,
        run_id: str,
        *,
        status: str,
        error: str | None = None,
        error_type: str | None = None,
        worker_id: str | None = None,
    ) -> tuple[AgentRun | None, bool]:
        """写入 Run 终态，并关闭当前 attempt。

        有 attempt 时以 attempt 的 owner 和租约作为 fencing；没有 attempt 的
        旧 Run（迁移前已认领）退回 Run 级 owner/租约校验，保证滚动升级窗口。
        """

        if status not in AGENT_RUN_TERMINAL_STATUSES:
            raise ValueError(f"不支持的 Agent Run 终态：{status}")

        current_time = datetime.now(UTC)
        run = await self._lock_update(run_id)
        if run is None:
            return None, False
        current_status = str(run.agent_status)
        if current_status in AGENT_RUN_TERMINAL_STATUSES:
            await self.attempts.close_open(
                run_id,
                status="orphaned",
                error="Run was already terminal while its attempt was open",
                error_type="OrphanedAttempt",
                now=current_time,
            )
            return run, False
        if run.worker_id != worker_id:
            return run, False
        # 未认领的 Run 仅允许由入队失败路径写入失败终态。
        if worker_id is None and (
            current_status not in {"pending", "queued"} or status != "failed"
        ):
            return run, False

        attempt = None
        if worker_id is not None:
            attempt = await self.attempts.open(
                run_id,
                worker_id=worker_id,
                for_update=True,
            )
            if attempt is not None:
                if (
                    attempt.lease_expires_at is None
                    or _as_utc(attempt.lease_expires_at) <= _as_utc(current_time)
                ):
                    return run, False
            else:
                lease = getattr(run, "lease_expires_at", None)
                if lease is not None and _as_utc(lease) <= _as_utc(current_time):
                    return run, False

        # FIXEME: interrupted 复用现有 error/error_type 终态消息字段，不增加专用参数。
        if status == "interrupted" and error is not None:
            interrupt_payload = json.loads(error)
            if not isinstance(interrupt_payload, dict):
                raise ValueError("interrupted 终态消息必须是 JSON 对象")
            run.run_metadata = {
                **dict(run.run_metadata or {}),
                "interrupt": interrupt_payload,
            }
        run.agent_status = status  # ty: ignore[invalid-assignment]
        run.finished_at = current_time  # ty: ignore[invalid-assignment]
        run.error = error  # ty: ignore[invalid-assignment]
        run.error_type = error_type  # ty: ignore[invalid-assignment]
        # 终态即释放租约，避免过期收敛重复处理同一个 Run。
        run.heartbeat_at = None  # ty: ignore[invalid-assignment]
        run.lease_expires_at = None  # ty: ignore[invalid-assignment]
        if attempt is not None:
            await self.attempts.close(
                attempt,
                status=status,
                error=error,
                error_type=error_type,
                now=current_time,
            )
        else:
            await self.attempts.close_open(
                run_id,
                status=status,
                error=error,
                error_type=error_type,
                now=current_time,
            )
        # 终态 reconcile：同一事务内收敛残留的 running 审计行。
        await self.close_running_audit_messages(
            run_id, execution_status=_audit_terminal_status(status)
        )
        await self.session.flush()
        return run, True

    async def request_cancel(self, run_id: str) -> AgentRun | None:
        run = await self._lock_update(run_id)
        if run is None:
            return None
        if str(run.agent_status) in AGENT_RUN_TERMINAL_STATUSES:
            return run

        run.agent_status = "cancel_requested"
        await self.session.flush()
        return run
