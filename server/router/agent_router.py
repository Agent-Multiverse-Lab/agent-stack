from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from server.entities.agent import AgentRunCreateRequest, AgentRunResumeRequest
from server.service.agent_run_service import (
    AgentRunConflictError,
    cancel_run_service,
    create_agent_run_service,
    create_resume_agent_run_service,
    stream_agent_run_events,
)
from server.utils.auth import AuthenticatedUser
from src.configs import config
from src.database import get_db
from src.database.repositories import AgentRunRepository

agent_router = APIRouter(prefix="/agent", tags=["agent_router"])


@agent_router.post("")
def create_agent():
    """预留用户自定义 Agent 入口。"""


@agent_router.post("/runs")
async def create_agent_run(
    agentrun_request: AgentRunCreateRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """创建持久化 Agent Run，并在事务提交后入队。"""
    if not config.enable_run_queue:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="请开启 ARQ 队列模式",
        )

    try:
        run = await create_agent_run_service(
            db=db,
            current_user=current_user,
            query=agentrun_request.query,
            agent_id=agentrun_request.agent_id,
            thread_id=agentrun_request.thread_id,
            thread_metadata=agentrun_request.thread_metadata,
            image_content=agentrun_request.image_content,
            msg_metadata=agentrun_request.msg_metadata,
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
        "thread_id": run.thread_id,
        "status": run.agent_status,
        "request_id": run.request_id,
        "stream_url": (
            f"/api/agent/runs/{run.id}/events?thread_id={run.thread_id}"
        ),
    }


@agent_router.post("/runs/{interrupted_run_id}/resume")
async def resume_agent_run(
    interrupted_run_id: str,
    resume_request: AgentRunResumeRequest,
    current_user: AuthenticatedUser,
    db: AsyncSession = Depends(get_db),
):
    """创建新的 Resume Run，并继续父 Run 所在 checkpoint。"""
    if not config.enable_run_queue:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="请开启 ARQ 队列模式",
        )

    # FIXEME: Resume 保持独立入口，普通 Run 创建接口不再猜测恢复语义。
    try:
        run = await create_resume_agent_run_service(
            db=db,
            current_user=current_user,
            interrupted_run_id=interrupted_run_id,
            thread_id=resume_request.thread_id,
            thread_metadata=resume_request.thread_metadata,
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
        "parent_run_id": run.parent_run_id,
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
        return await cancel_run_service(
            run_id=run_id,
            current_user_id=current_user.uid,
            db=db,
        )
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
        stream_agent_run_events(
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
