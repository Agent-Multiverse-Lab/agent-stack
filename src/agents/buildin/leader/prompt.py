from datetime import datetime
from zoneinfo import ZoneInfo

from src.agents.buildin.leader.prompts.v6 import (
    FILESYSTEM_CONTEXT_PROMPT,
    ORCHESTRATOR_AGENT_SYSTEM_PROMPT,
)
from src.agents.buildin.leader.prompts.v6 import (
    TODO_MIDDLEWARE_SYSTEM_PROMPT as TODO_MIDDLEWARE_SYSTEM_PROMPT,
)


def build_prompt(context) -> str:
    current_time = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"当前时间：{current_time}\n\n"
        f"{ORCHESTRATOR_AGENT_SYSTEM_PROMPT}\n\n"
        f"{FILESYSTEM_CONTEXT_PROMPT}\n\n"
        f"{context.system_prompt or ''}"
    )
