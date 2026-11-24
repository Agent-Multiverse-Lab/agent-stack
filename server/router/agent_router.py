from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from server.entities.agent import (
    AgentContext,
    AgentResponse,
    AgentRunCreateRequest,
    AgentUpdateRequest,
    QueuedAgentRunResponse,
)
from server.exception import AgentRunConflictError
from server.service import (
    agent_run_request_queue_service,
    agent_run_request_service,
    agent_run_service,
)
from server.service.agent_service import get_agent_context
from server.utils.auth import AuthenticatedUser
from src.configs import config
from src.database import get_db
from src.database.repositories import AgentRepository, AgentRunRepository

agent_router = APIRouter(prefix="/agent", tags=["agent_router"])


@agent_router.get("", response_model=list[AgentResponse], response_model_exclude_none=True)
async def list_agents(
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
) -> list[AgentResponse]:
    """读取已认证用户可查看的数据库 Agent 列表。"""
    repository = AgentRepository(db)
    agents = await repository.list_main_agents()
    subagents = await repository.list_subagents()
    return [
        AgentResponse(
            id=agent.slug,
            name=agent.name,
            description=agent.description,
            is_subagent=agent.is_subagent,
            enabled=agent.enabled,
        )
        for agent in (*agents, *subagents)
    ]


@agent_router.get("/{agent_id}/context", response_model=AgentContext)
async def read_agent_context(
    agent_id: str,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
) -> AgentContext:
    """读取已认证用户查看的 Agent 基础配置。"""
    context = await get_agent_context(db, agent_id)
    if context is None:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return context


@agent_router.patch("/{agent_id}", response_model=AgentResponse, response_model_exclude_none=True)
async def update_agent(
    agent_id: str,
    payload: AgentUpdateRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """保存已认证用户对 Agent 基础字段的修改。"""
    agent = await AgentRepository(db).update_agent(
        agent_id,
        **payload.model_dump(exclude_unset=True),
    )
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent 不存在")
    await db.commit()
    await db.refresh(agent)
    return AgentResponse(
        id=agent.slug,
        name=agent.name,
        description=agent.description,
        is_subagent=agent.is_subagent,
        enabled=agent.enabled,
    )


@agent_router.post("/runs")
async def create_agent_run(
    agentrun_request: AgentRunCreateRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """按会话状态和策略接收请求，创建 Run 提交后入队。"""
    if not config.enable_run_queue:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="请开启队列模式",
        )

    try:
        run = await agent_run_request_service.submit_agent_run_request(
            db=db,
            current_user=current_user,
            query=agentrun_request.query,
            agent_id=agentrun_request.agent_id,
            thread_id=agentrun_request.thread_id,
            request_metadata=agentrun_request.request_metadata,
            image_content=agentrun_request.image_content,
            dispatch_policy=agentrun_request.dispatch_policy,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except AgentRunConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if isinstance(run, QueuedAgentRunResponse):
        return JSONResponse(status_code=202, content=run.model_dump())

    return {
        "run_id": run.id,
        "thread_id": run.thread_id,
        "status": run.agent_status,
        "request_id": run.request_id,
        "stream_url": (
            f"/api/agent/runs/{run.id}/events?thread_id={run.thread_id}"
        ),
    }


def _conflict_response(exc: AgentRunConflictError) -> JSONResponse:
    if exc.run_id is not None:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc), "run_id": exc.run_id},
        )
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(exc),
    )


@agent_router.delete("/runs/requests/{request_id}")
async def cancel_queued_agent_run_request(
    request_id: str,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """逻辑软取消等待区中的排队请求及其未绑定输入消息。"""
    try:
        return await agent_run_request_queue_service.cancel_queued_request(
            db=db,
            current_user=current_user,
            request_id=request_id,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except AgentRunConflictError as exc:
        return _conflict_response(exc)


@agent_router.post("/runs/requests/{request_id}/steer")
async def steer_queued_agent_run_request(
    request_id: str,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """将等待区请求原地升级为 steer，或在会话空闲时就地晋升执行。"""
    if not config.enable_run_queue:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="请开启 ARQ 队列模式",
        )

    try:
        result = await agent_run_request_queue_service.steer_queued_request(
            db=db,
            current_user=current_user,
            request_id=request_id,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except AgentRunConflictError as exc:
        return _conflict_response(exc)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if isinstance(result, QueuedAgentRunResponse):
        return JSONResponse(status_code=202, content=result.model_dump())

    return {
        "run_id": result.id,
        "thread_id": result.thread_id,
        "status": result.agent_status,
        "request_id": result.request_id,
        "stream_url": (
            f"/api/agent/runs/{result.id}/events?thread_id={result.thread_id}"
        ),
    }


@agent_router.post("/runs/{interrupted_run_id}/resume")
async def resume_agent_run(
    interrupted_run_id: str,
    resume_request: AgentRunCreateRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """创建新的 Resume Run，并继续父 Run 所在 checkpoint。"""
    if not config.enable_run_queue:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="请开启 ARQ 队列模式",
        )

    try:
        run = await agent_run_service.create_resume_agent_run(
            db=db,
            current_user=current_user,
            interrupted_run_id=interrupted_run_id,
            agent_id=resume_request.agent_id,
            thread_id=resume_request.thread_id,
            request_metadata=resume_request.request_metadata,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except AgentRunConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return {
        "run_id": run.id,
        "run_type": run.run_type,
        "created_by_run_id": run.created_by_run_id,
        "thread_id": run.thread_id,
        "status": run.agent_status,
        "request_id": run.request_id,
        "stream_url": (
            f"/api/agent/runs/{run.id}/events?thread_id={run.thread_id}"
        ),
    }


@agent_router.post("/runs/{run_id}/cancel")
async def cancel_agent_run(
    run_id: str,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """请求取消当前用户的 Agent Run。"""
    try:
        return await agent_run_service.cancel_agent_run(
            run_id=run_id,
            current_user_id=current_user.uid,
            db=db,
        )
    except AgentRunConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@agent_router.get("/runs/{run_id}/events")
async def stream_run_event(
    run_id: str,
    thread_id: str,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """读取当前用户 Agent Run 的 SSE 事件。"""
    run = await AgentRunRepository(db).get_by_id_for_user_and_thread(
        run_id=run_id,
        uid=current_user.uid,
        thread_id=thread_id,
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Agent Run 不存在")

    return StreamingResponse(
        agent_run_service.stream_agent_run_events(
            run_id=run_id,
            current_uid=current_user.uid,
            thread_id=thread_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
