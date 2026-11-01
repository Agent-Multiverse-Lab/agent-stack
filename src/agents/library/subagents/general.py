"""动态委派任务共用的执行身份与初始配置。"""

from src.agents.library import AgentLibrary

GENERIC_AGENT_SLUG = "generic_agent"

GENERIC_AGENT = AgentLibrary(
    slug=GENERIC_AGENT_SLUG,
    name="通用任务执行器",
    description="根据 Leader 分配的任务、工具和上下文执行独立子任务",
    backend_id="SubAgentGraph",
    context={
        "system_prompt": (
            "你负责执行 Leader 分配的独立子任务。围绕收到的任务和上下文工作，"
            "使用本次分配的工具，向 Leader 返回可核验的结果、产物位置和仍未解决的问题。"
            "缺少必要信息时明确说明，不编造事实或执行结果。面向用户的最终答复由 Leader 负责。"
        ),
        "tools": [],
    },
)
