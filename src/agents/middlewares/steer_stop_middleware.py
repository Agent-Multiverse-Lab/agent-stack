"""在下一轮 model 前结束被转向的 Run，保留已完成的工具轮次。"""

from typing import NotRequired

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config

from src.database.repositories import AgentRunRequestRepository
from src.database.session import session_context


class SteerState(AgentState):
    steered_run_id: NotRequired[str]


class SteerStopMiddleware(AgentMiddleware):
    state_schema = SteerState

    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state, runtime):
        async with session_context() as db:
            should_stop = await AgentRunRequestRepository(db).has_queued_steer_for_thread(
                runtime.context.thread_id,
            )
        if should_stop:
            return {"jump_to": "end", "steered_run_id": runtime.context.run_id}
        return None
