"""ToolMessage 生命周期审计 Repository。

以当前 Run 的 lease 归属为边界，增量落库每次 Tool 调用的顺序、状态、输入输出与
单调耗时。
审计行使用 message_type=tool_audit 与普通会话历史隔离；Agent Stack 的 ToolCall
投影仍由终态 checkpoint 落库拥有，本仓储只负责审计事实，不建立兼容投影。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import TOOL_AUDIT_MESSAGE_TYPE, Message
from src.database.repositories.agent_run_repository import AgentRunRepository


class ToolMessageAuditRepository:
    """以当前 Run lease 为边界持久化 ToolMessage 生命周期。"""

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
        tool_call_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        sequence: int,
        started_at: datetime,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[Message, bool]:
        """幂等创建 running 的 Tool 审计消息。"""
        operation_id = tool_call_id.strip()
        normalized_name = tool_name.strip()
        if not operation_id:
            raise ValueError("Tool tool_call_id 不能为空")
        if not normalized_name:
            raise ValueError("Tool tool_name 不能为空")
        if sequence < 0:
            raise ValueError("Tool sequence 不能为负数")

        run = await self._lock_run(
            run_id=run_id,
            request_id=request_id,
            thread_id=thread_id,
            worker_id=worker_id,
        )
        existing = await self._get(run_id, operation_id)
        if existing is not None:
            self._require_same_owner(
                existing,
                conversation_id=int(run.conversation_id),
                request_id=request_id,
            )
            self._require_same_start(
                existing,
                tool_name=normalized_name,
                tool_input=tool_input,
                sequence=sequence,
            )
            return existing, False

        message = Message(
            conversation_id=int(run.conversation_id),
            agent_run_id=run.id,
            role="tool",
            content="",
            message_type=TOOL_AUDIT_MESSAGE_TYPE,
            msg_metadata={
                **dict(metadata or {}),
                "audit_kind": "tool",
                "tool_call_id": operation_id,
                "tool_name": normalized_name,
                "input": dict(tool_input),
            },
            request_id=request_id,
            status="completed",
            operation_id=operation_id,
            started_at=started_at,
            sequence=sequence,
            execution_status="running",
        )
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        return message, True

    async def complete(
        self,
        *,
        run_id: str,
        request_id: str,
        thread_id: str,
        worker_id: str,
        tool_call_id: str,
        output: Any,
        content: str,
        finished_at: datetime,
        duration_ms: int | None,
        finished_sequence: int | None,
    ) -> Message:
        """完成同一 Tool 审计消息（成功）。"""
        return await self._finish(
            run_id=run_id,
            request_id=request_id,
            thread_id=thread_id,
            worker_id=worker_id,
            tool_call_id=tool_call_id,
            execution_status="completed",
            output=output,
            content=content,
            error_message=None,
            finished_at=finished_at,
            duration_ms=duration_ms,
            finished_sequence=finished_sequence,
        )

    async def fail(
        self,
        *,
        run_id: str,
        request_id: str,
        thread_id: str,
        worker_id: str,
        tool_call_id: str,
        error_message: str,
        output: Any,
        content: str,
        finished_at: datetime,
        duration_ms: int | None,
        finished_sequence: int | None,
    ) -> Message:
        """关闭失败 Tool 审计消息。"""
        return await self._finish(
            run_id=run_id,
            request_id=request_id,
            thread_id=thread_id,
            worker_id=worker_id,
            tool_call_id=tool_call_id,
            execution_status="failed",
            output=output,
            content=content,
            error_message=error_message,
            finished_at=finished_at,
            duration_ms=duration_ms,
            finished_sequence=finished_sequence,
        )

    async def observe_error(
        self,
        *,
        run_id: str,
        request_id: str,
        thread_id: str,
        worker_id: str,
        tool_call_id: str,
        error_message: str,
        finished_at: datetime,
        duration_ms: int | None,
        finished_sequence: int,
    ) -> Message:
        """保存裸 tool-error，最终状态由 Run 终态收敛裁决。"""
        operation_id = tool_call_id.strip()
        if not operation_id:
            raise ValueError("Tool tool_call_id 不能为空")
        if duration_ms is not None and duration_ms < 0:
            raise ValueError("Tool duration_ms 不能为负数")
        if finished_sequence < 0:
            raise ValueError("Tool finished_sequence 不能为负数")

        run = await self._lock_run(
            run_id=run_id,
            request_id=request_id,
            thread_id=thread_id,
            worker_id=worker_id,
        )
        message = await self._get(run_id, operation_id)
        if message is None:
            raise ValueError("Tool error 缺少对应的 start 事实")
        self._require_same_owner(
            message,
            conversation_id=int(run.conversation_id),
            request_id=request_id,
        )
        metadata = dict(message.msg_metadata or {})
        if message.execution_status != "running":
            if metadata.get("error_message") != error_message:
                raise ValueError("已关闭 Tool 审计事实不能被不同错误覆盖")
            return message

        metadata["error_message"] = error_message
        metadata["finished_sequence"] = finished_sequence
        metadata["awaiting_run_terminal"] = True
        message.msg_metadata = metadata
        message.finished_at = finished_at
        message.duration_ms = duration_ms
        await self.db.flush()
        await self.db.refresh(message)
        return message

    async def get(self, *, run_id: str, operation_id: str) -> Message | None:
        """按同一 Run 的 tool_call_id 读取审计消息。"""
        return await self._get(run_id, operation_id)

    async def list_for_run(self, run_id: str) -> list[Message]:
        """按 ProtocolEvent sequence 返回 Run 的 Tool 时间线。"""
        result = await self.db.execute(
            select(Message)
            .where(
                Message.agent_run_id == run_id,
                Message.message_type == TOOL_AUDIT_MESSAGE_TYPE,
                Message.role == "tool",
            )
            .order_by(Message.sequence.asc(), Message.id.asc())
        )
        return list(result.scalars().all())

    async def _finish(
        self,
        *,
        run_id: str,
        request_id: str,
        thread_id: str,
        worker_id: str,
        tool_call_id: str,
        execution_status: Literal["completed", "failed"],
        output: Any,
        content: str,
        error_message: str | None,
        finished_at: datetime,
        duration_ms: int | None,
        finished_sequence: int | None,
    ) -> Message:
        """原子关闭 Tool 审计事实。"""
        operation_id = tool_call_id.strip()
        if not operation_id:
            raise ValueError("Tool tool_call_id 不能为空")
        if duration_ms is not None and duration_ms < 0:
            raise ValueError("Tool duration_ms 不能为负数")
        if finished_sequence is not None and finished_sequence < 0:
            raise ValueError("Tool finished_sequence 不能为负数")

        run = await self._lock_run(
            run_id=run_id,
            request_id=request_id,
            thread_id=thread_id,
            worker_id=worker_id,
        )
        message = await self._get(run_id, operation_id)
        if message is None:
            raise ValueError("Tool terminal 缺少对应的 start 事实")
        self._require_same_owner(
            message,
            conversation_id=int(run.conversation_id),
            request_id=request_id,
        )

        metadata = dict(message.msg_metadata or {})
        if message.execution_status == execution_status:
            if (
                message.content != content
                or metadata.get("error_message") != error_message
                or _canonical_tool_output(metadata.get("output"))
                != _canonical_tool_output(output)
            ):
                raise ValueError("已关闭 Tool 审计事实不能被不同结果覆盖")
            return message
        if message.execution_status != "running":
            raise ValueError(
                f"Tool 审计事实不能从 {message.execution_status} 转为 {execution_status}"
            )

        message.content = content
        message.finished_at = message.finished_at or finished_at
        if duration_ms is not None:
            message.duration_ms = duration_ms
        message.execution_status = execution_status
        metadata["output"] = output
        metadata["error_message"] = error_message
        if finished_sequence is not None:
            metadata["finished_sequence"] = finished_sequence
        message.msg_metadata = metadata
        await self.db.flush()
        await self.db.refresh(message)
        return message

    async def _get(self, run_id: str, operation_id: str) -> Message | None:
        result = await self.db.execute(
            select(Message)
            .where(
                Message.agent_run_id == run_id,
                Message.operation_id == operation_id,
                Message.role == "tool",
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
            or message.role != "tool"
        ):
            raise ValueError("Tool 审计消息必须属于同一 Run、request 和 conversation")

    @staticmethod
    def _require_same_start(
        message: Message,
        *,
        tool_name: str,
        tool_input: dict[str, Any],
        sequence: int,
    ) -> None:
        metadata = message.msg_metadata if isinstance(message.msg_metadata, dict) else {}
        if (
            metadata.get("tool_name") != tool_name
            or metadata.get("input") != tool_input
            or message.sequence != sequence
        ):
            raise ValueError("重复 Tool start 与已持久化事实不一致")


def _canonical_tool_output(output: Any) -> Any:
    """忽略 LangGraph 写入 State 时补充的 ToolMessage id/name。"""
    if not isinstance(output, dict):
        return output
    return {key: value for key, value in output.items() if key not in {"id", "name"}}
