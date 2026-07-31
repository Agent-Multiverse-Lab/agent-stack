"""通过工具把父智能体的独立任务委派给后台子智能体 Run。"""

import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from deepagents.middleware._utils import append_to_system_message
from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)
from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from server.service.agent_run_service import (
    get_agent_run_result,
    read_subagent_progress,
    request_cancel_agent_run,
    wait_agent_run_result,
)
from server.service.input_message_service import build_agent_input_msg
from src.agents.base_agent import BaseAgent
from src.agents.base_context import BaseContext
from src.database.session import session_context

TASK_SYSTEM_PROMPT = """## 子智能体任务编排

你可以将边界清晰、能够独立完成的任务交给合适的子智能体处理，并负责安排执行顺序、跟踪运行状态和整合最终结果。

- 简单任务直接完成，不要进行不必要的委派。
- 后续步骤立即依赖子任务结果时，使用 `task` 启动子智能体并等待最终文本。
- 长时间运行或彼此独立的任务，使用 `subagent_start` 在后台启动，并保存返回的 `run_id`。
- 使用 `subagent_status` 查询后台任务的生命周期状态、最近进度和已完成结果。
- 不再需要某个后台任务时，使用 `subagent_cancel` 请求取消。
- 明确需要后台任务的最终结果时，使用 `subagent_await` 等待并取得最终文本。
- 每次调用必须选择可用的 `subagent_slug`，任务描述应包含必要上下文、目标、执行边界、输出要求和完成标准。
- 收到子智能体结果后，检查其完整性和一致性；不要直接拼接未经整理或互相冲突的结果。
- 不要通过 HTTP、shell 或命令行绕过这些工具调用子智能体。
"""


class TaskInput(BaseModel):
    description: str = Field(description="子智能体可独立执行的完整任务")
    subagent_slug: str = Field(description="要执行的子智能体 slug")


class SubAgentRunInput(BaseModel):
    run_id: str = Field(description="由 task 或 subagent_start 返回的子运行 ID")


def _subagent_run_service(db: AsyncSession):
    """延迟加载 service，并绑定当前数据库会话。"""

    from server.service.subagent_service import SubAgentRunService

    return SubAgentRunService(db)


class SubAgentMiddleware(AgentMiddleware[Any, Any, Any]):
    """把模型工具调用适配为持久化、入队的子智能体 Run。"""

    def __init__(
        self,
        *,
        subagents: Sequence[BaseAgent],
        parent_context: BaseContext,
        system_prompt: str | None = TASK_SYSTEM_PROMPT,
    ) -> None:
        super().__init__()
        if not subagents:
            raise ValueError("必须至少指定一个子智能体")

        self._subagents: dict[str, BaseAgent] = {}
        for subagent in subagents:
            subagent_slug = subagent.name
            if subagent_slug in self._subagents:
                raise ValueError(f"子智能体 slug 重复：{subagent_slug}")
            self._subagents[subagent_slug] = subagent

        self.parent_context = parent_context
        self.subagent_slugs = frozenset(self._subagents)
        self.system_prompt = system_prompt
        self.tools: list[BaseTool] = self._build_subagent_tools()

    def _build_subagent_tools(self) -> list[BaseTool]:
        return [
            self._create_task_tool(),
            self._create_start_tool(),
            self._create_status_tool(),
            self._create_cancel_tool(),
            self._create_await_tool(),
        ]

    def _create_task_tool(self) -> StructuredTool:
        async def task(
            description: str,
            subagent_slug: str,
            runtime: ToolRuntime,
        ) -> Command:
            subagent_record, error = await self._start_run(
                description=description,
                subagent_slug=subagent_slug,
                runtime=runtime,
                tool_name="task",
            )
            if error is not None:
                return error

            run_id = str(subagent_record["run_id"])  # ty:ignore[not-subscriptable]
            try:
                result = await wait_agent_run_result(run_id)
            except Exception as exc:
                return self._result(
                    runtime=runtime,
                    tool_name="task",
                    subagent_slug=subagent_slug,
                    content=f"子智能体运行未能返回结果：{exc}",
                    record={**subagent_record, "status": "failed"},  # ty:ignore[invalid-argument-type]
                    status="failed",
                    error=True,
                )

            return self._result(
                runtime=runtime,
                tool_name="task",
                subagent_slug=subagent_slug,
                content=result or "子智能体已完成，但没有返回文本结果。",
                record={**subagent_record, "status": "completed"},
                status="completed",
            )

        return StructuredTool.from_function(
            name="task",
            coroutine=task,
            description=(
                f"启动一个子智能体任务并等待最终文本；适合父智能体后续步骤立即依赖结果的任务。\n\n可用子智能体：\n{self._available_agents()}"
            ),
            args_schema=TaskInput,
            infer_schema=False,
        )

    def _create_start_tool(self) -> StructuredTool:
        async def subagent_start(
            description: str,
            subagent_slug: str,
            runtime: ToolRuntime,
        ) -> Command:
            return await self._enqueue_task(
                description=description,
                subagent_slug=subagent_slug,
                runtime=runtime,
                tool_name="subagent_start",
            )

        return StructuredTool.from_function(
            name="subagent_start",
            coroutine=subagent_start,
            description=(
                f"在后台启动一个子智能体任务并立即返回 run_id；适合长任务或可并行任务。\n\n可用子智能体：\n{self._available_agents()}"
            ),
            args_schema=TaskInput,
            infer_schema=False,
        )

    def _create_status_tool(self) -> StructuredTool:
        async def subagent_status(
            run_id: str,
        ) -> str:
            try:
                async with session_context() as db:
                    service = _subagent_run_service(db)
                    parent_run = await service.get_parent_run(
                        parent_run_id=self.parent_context.run_id,
                    )
                    child_run_status = await service.get_child_run_status(
                        parent_run_id=str(parent_run.id),
                        run_id=run_id,
                    )
                    parent_uid = str(parent_run.uid)
                progress = await read_subagent_progress(
                    run_id=run_id,
                )
                result = None
                if (
                    progress["status"] == "completed"
                    or child_run_status["status"] == "completed"
                ):
                    result = await get_agent_run_result(
                        current_uid=parent_uid,
                        run_id=run_id,
                    )
            except Exception as exc:
                return json.dumps(
                    {"status": "error", "run_id": run_id, "error": str(exc)},
                    ensure_ascii=False,
                )
            return json.dumps(
                {
                    **progress,
                    **child_run_status,
                    "events": progress["events"],
                    "result": result,
                },
                ensure_ascii=False,
            )

        return StructuredTool.from_function(
            name="subagent_status",
            coroutine=subagent_status,
            description="查询当前父运行创建的子智能体 Run 状态、最近进度和已完成结果。",
            args_schema=SubAgentRunInput,
            infer_schema=False,
        )

    def _create_cancel_tool(self) -> StructuredTool:
        async def subagent_cancel(
            run_id: str,
            runtime: ToolRuntime,
        ) -> Command:
            child_run_status: Mapping[str, Any] | None = None
            try:
                async with session_context() as db:
                    service = _subagent_run_service(db)
                    parent_run = await service.get_parent_run(
                        parent_run_id=self.parent_context.run_id,
                    )
                    child_run_status = await service.get_child_run_status(
                        parent_run_id=str(parent_run.id),
                        run_id=run_id,
                    )
                    parent_uid = str(parent_run.uid)
                    cancelled_run = await request_cancel_agent_run(
                        run_id=run_id,
                        current_uid=parent_uid,
                        db=db,
                    )
                    cancel_status = str(cancelled_run.agent_status)
            except Exception as exc:
                return self._result(
                    runtime=runtime,
                    tool_name="subagent_cancel",
                    subagent_slug=(
                        str(child_run_status["agent_slug"])
                        if child_run_status
                        else "unknown"
                    ),
                    content=f"无法取消子智能体运行：{exc}",
                    run_id=run_id,
                    status="failed",
                    error=True,
                )

            return self._result(
                runtime=runtime,
                tool_name="subagent_cancel",
                subagent_slug=str(child_run_status["agent_slug"]),
                content=json.dumps(
                    {
                        "run_id": str(cancelled_run.id),
                        "status": cancel_status,
                    },
                    ensure_ascii=False,
                ),
                run_id=str(cancelled_run.id),
                status=cancel_status,
            )

        return StructuredTool.from_function(
            name="subagent_cancel",
            coroutine=subagent_cancel,
            description="请求取消当前父运行创建的后台子智能体 Run。",
            args_schema=SubAgentRunInput,
            infer_schema=False,
        )

    def _create_await_tool(self) -> StructuredTool:
        async def subagent_await(
            run_id: str,
            runtime: ToolRuntime,
        ) -> Command:
            child_run_status: Mapping[str, Any] | None = None
            try:
                async with session_context() as db:
                    child_run_status = await _subagent_run_service(
                        db
                    ).get_child_run_status(
                        parent_run_id=self.parent_context.run_id,
                        run_id=run_id,
                    )
                result = await wait_agent_run_result(run_id)
            except Exception as exc:
                return self._result(
                    runtime=runtime,
                    tool_name="subagent_await",
                    subagent_slug=(
                        str(child_run_status["agent_slug"])
                        if child_run_status
                        else "unknown"
                    ),
                    content=f"无法取得子智能体结果：{exc}",
                    run_id=run_id,
                    status="failed",
                    error=True,
                )

            return self._result(
                runtime=runtime,
                tool_name="subagent_await",
                subagent_slug=str(child_run_status["agent_slug"]),
                content=result or "子智能体已完成，但没有返回文本结果。",
                run_id=run_id,
                status="completed",
            )

        return StructuredTool.from_function(
            name="subagent_await",
            coroutine=subagent_await,
            description="等待当前父运行创建的后台子智能体 Run，并返回最终文本。",
            args_schema=SubAgentRunInput,
            infer_schema=False,
        )

    async def _enqueue_task(
        self,
        *,
        description: str,
        subagent_slug: str,
        runtime: ToolRuntime,
        tool_name: str = "subagent_start",
    ) -> Command:
        """启动子 Run 后立即返回；保留为后台启动路径的单一实现。"""

        subagent_record, error = await self._start_run(
            description=description,
            subagent_slug=subagent_slug,
            runtime=runtime,
            tool_name=tool_name,
        )
        if error is not None:
            return error
        return self._result(
            runtime=runtime,
            tool_name=tool_name,
            subagent_slug=subagent_slug,
            content=json.dumps(subagent_record, ensure_ascii=False),
            record=subagent_record,
            status=str(subagent_record["status"]),  # ty:ignore[not-subscriptable]
        )

    async def _start_run(
        self,
        *,
        description: str,
        subagent_slug: str,
        runtime: ToolRuntime,
        tool_name: str,
    ) -> tuple[Mapping[str, Any] | None, Command | None]:
        if not runtime.tool_call_id:
            raise ValueError("子智能体工具调用缺少 tool_call_id")

        subagent = self._subagents.get(subagent_slug)
        if subagent is None:
            allowed = "、".join(self._subagents)
            return None, self._result(
                runtime=runtime,
                tool_name=tool_name,
                subagent_slug=subagent_slug,
                content=f"未知子智能体：{subagent_slug}；可用项：{allowed}",
                status="failed",
                error=True,
            )

        try:
            async with session_context() as db:
                subagent_record = await _subagent_run_service(
                    db
                ).create_subagent_record(
                    parent_run_id=self.parent_context.run_id,
                    agent_slug=subagent_slug,
                    input_message=build_agent_input_msg(query=description),
                    uid=self.parent_context.uid,
                    tool_call_id=runtime.tool_call_id,
                    request_id=self.parent_context.request_id,
                )
        except Exception as exc:
            return None, self._result(
                runtime=runtime,
                tool_name=tool_name,
                subagent_slug=subagent_slug,
                content=f"无法启动子智能体 {subagent_slug}：{exc}",
                status="failed",
                error=True,
            )
        return subagent_record, None

    @staticmethod
    def _result(
        *,
        runtime: ToolRuntime,
        tool_name: str,
        subagent_slug: str,
        content: str,
        status: str,
        record: Mapping[str, Any] | None = None,
        run_id: str | None = None,
        error: bool = False,
    ) -> Command:
        if not runtime.tool_call_id:
            raise ValueError("子智能体工具调用缺少 tool_call_id")

        resolved_run_id = run_id
        if resolved_run_id is None and record is not None:
            value = record.get("run_id")
            resolved_run_id = str(value) if value is not None else None

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=content,
                        tool_call_id=runtime.tool_call_id,
                        name=tool_name,
                        status="error" if error else "success",
                        additional_kwargs={
                            "subagent_slug": subagent_slug,
                            "subagent_run_id": resolved_run_id,
                            "subagent_status": status,
                            "subagent_record": dict(record) if record else None,
                        },
                    )
                ]
            }
        )

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        if self.system_prompt is None:
            return handler(request)
        return handler(
            request.override(
                system_message=append_to_system_message(
                    request.system_message,
                    self._system_prompt(),
                )
            )
        )

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[
            [ModelRequest[Any]],
            Awaitable[ModelResponse[Any]],
        ],
    ) -> ModelResponse[Any]:
        if self.system_prompt is None:
            return await handler(request)
        return await handler(
            request.override(
                system_message=append_to_system_message(
                    request.system_message,
                    self._system_prompt(),
                )
            )
        )

    def _available_agents(self) -> str:
        return "\n".join(
            f"- {subagent_slug}: {subagent.description}"
            for subagent_slug, subagent in self._subagents.items()
        )

    def _system_prompt(self) -> str:
        return f"{self.system_prompt}\n可用子智能体：\n{self._available_agents()}"


def create_subagent_middleware(
    *,
    subagents: Sequence[BaseAgent],
    parent_context: BaseContext,
    system_prompt: str | None = TASK_SYSTEM_PROMPT,
) -> SubAgentMiddleware:
    """创建绑定父 Agent context 的子智能体中间件。"""

    return SubAgentMiddleware(
        subagents=subagents,
        parent_context=parent_context,
        system_prompt=system_prompt,
    )
