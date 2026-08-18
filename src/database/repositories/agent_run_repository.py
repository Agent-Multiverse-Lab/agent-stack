from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.database.models import AgentRun, Conversation

AGENT_RUN_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})


class AgentRunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, run_id: str) -> AgentRun | None:
        result = await self.session.execute(
            select(AgentRun)
            .where(AgentRun.id == run_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

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
        trigger_message_id: int,
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

    async def set_running(self, run_id: str) -> AgentRun | None:
        run = await self._lock_update(run_id)
        if run is None:
            return None
        if str(run.agent_status) in AGENT_RUN_TERMINAL_STATUSES | {
            "cancel_requested"
        }:
            return run

        run.agent_status = "running"
        run.started_at = run.started_at or datetime.now(UTC)
        run.error = None
        await self.session.flush()
        return run

    async def set_agent_terminal(
        self,
        run_id: str,
        *,
        status: str,
        error: str | None = None,
        error_type: str | None = None,
    ) -> tuple[AgentRun | None, bool]:
        if status not in AGENT_RUN_TERMINAL_STATUSES:
            raise ValueError(f"不支持的 Agent Run 终态：{status}")

        run = await self._lock_update(run_id)
        if run is None:
            return None, False
        current_status = str(run.agent_status)
        if current_status in AGENT_RUN_TERMINAL_STATUSES:
            return run, False

        run.agent_status = status  # ty: ignore[invalid-assignment]
        run.finished_at = datetime.now(UTC)  # ty: ignore[invalid-assignment]
        run.error = error  # ty: ignore[invalid-assignment]
        run.error_type = error_type  # ty: ignore[invalid-assignment]
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
