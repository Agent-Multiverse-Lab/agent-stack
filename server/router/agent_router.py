from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.service.agent_run_service import (
    cancel_run_service,
    enqueue_agent_run,
    stream_agent_run_events,
)
from server.utils.auth import AuthenticatedUser
from src.configs import config
from src.database import get_db
from src.database.models import Message, User
from src.database.repositories import AgentRunRepository, ConversationRepository

agent_router = APIRouter(prefix="/agent", tags=["agent_router"])


class AgentCreateRequest(BaseModel):
    # TODO 根据Agent字段创建 Agent创建实例
    pass
    

class AgentRunCreateRequest(BaseModel):
    query: str | None = Field(default=None, description="问题")
    agent_id: str = Field(default=..., description="agent的name")
    thread_id: str = Field(default=..., description="对话thraed_id")
    thread_metadata: dict = Field(default_factory=dict, description="附带参数")
    image_content: str | None = Field(None, description="图像文件")
    # model: str = Field(None, description="自选模型")
    is_resume: Any | None = Field(None, description="resume选项，用于特殊如Hil")
    parent_run_id: str | None = Field(None, description="父事件id,没有就自己的id")
    

@agent_router.post("")
def create_agent():
    """用户自己的创建智能体"""
    # TODO 待做，不需要也可，因为很多人不知道怎么才算合格
    pass


@agent_router.post("/runs")
async def create_agent_run(agentrun_request: AgentRunCreateRequest,
                    current_user: AuthenticatedUser,
                    db:AsyncSession = Depends(get_db)):
    """解耦对话的设计，这里创建消息事件流，前端只需拿着事件流去消费就可以。记住每次的新消息(上一事件完结后)
    都是做新的agent event id 以及 request_id,每次都是
    
    """
    
    # FIXME: /agent/runs 当前只实现 ARQ 的 run_id 驱动闭环，禁用队列时不要留下无法执行的 run。
    if not config.enable_run_queue:
        raise HTTPException(
            status_code=503,
            detail="请开启ARQ队列模式",
        )

    query = agentrun_request.query
    thread_id = agentrun_request.thread_id
    agent_id = agentrun_request.agent_id 
    thread_meatadata = agentrun_request.thread_metadata
    parent_run_id = agentrun_request.parent_run_id
    
    current_uid = current_user.uid
    
    conv_repo = ConversationRepository(db)
    
    # FIXME: 统一使用 request_id；兼容旧拼写键，避免现有调用立即失效。
    request_id = (
        thread_meatadata.get("request_id")
        or thread_meatadata.get("reuqest_id")
        or str(uuid.uuid4())
    )
        
    
    # TODO 创建 agent run 的
    if not thread_id:
        raise HTTPException(status_code=404, detail="会话id不可为空")
    
    conv_result = await conv_repo.get_conversation_by_thread_id_for_user(
        thread_id=thread_id,
        user_id=current_uid,
    )
    
    if not conv_result:
        raise HTTPException(status_code=404, detail="当前会话不存在或已删除")
    
    user_result = await db.execute(select(User).where(User.uid == str(current_uid)))
    
    if user_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # TODO 这里需要去解决创建事件的竞态问题，但是原型阶段不做任何防御和解决
    msg = Message(
        conversation_id=conv_result.id,
        role="user",
        content=query or "",
        image_content=agentrun_request.image_content,
        request_id=request_id,
        status="completed",
    )
    db.add(msg)
    await db.flush()
    
    # 存入消息后创建 run 记录
    run_repo = AgentRunRepository(db)
    run_id = str(uuid.uuid4())
    
    async with db.begin_nested():
        run = await run_repo.create_run(
            run_id=run_id,
            thread_id=thread_id,
            conversation_id=conv_result.id,  # ty:ignore[invalid-argument-type]
            uid=current_uid,  # ty:ignore[invalid-argument-type]
            agent_slug=agent_id,
            request_id=request_id,
            trigger_message_id=msg.id,  # ty:ignore[invalid-argument-type]
            run_type="chat",
            parent_run_id=parent_run_id,
        )
        # FIXME: 同时建立 Message -> AgentRun 关联，便于按 run 查询本次输入消息。
        msg.agent_run_id = run.id
    await db.commit()

    # FIXME: PostgreSQL 落库成功后再入队，确保 Worker 能按 run_id 恢复完整输入。
    await enqueue_agent_run(run.id)  # ty:ignore[invalid-argument-type]

    return {
        "run_id": run.id,
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
    """读取后端Redis生产的agent数据

    Args:
        run_id (str): 当权run_event
        current_user (AuthenticatedUser): _description_

    Returns:
        _type_: _description_
    """
    run_repo = AgentRunRepository(db)
    run = await run_repo.get_by_id_for_user_and_thread(
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

    

    
    

    
    
    
    
    
    
    
    
        
        
    
    

    
        
      

    
    
    
    
    
    

    
    
    
    
    
    
    
