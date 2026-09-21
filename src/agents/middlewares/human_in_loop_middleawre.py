"""项目自定义的人工审批中间件。"""


from langchain.agents.middleware import HumanInTheLoopMiddleware

SENSITIVE_BACKEND_TOOLS = ("write_file", "edit_file", "execute")
TOOL_APPROVAL_INTERRUPT_ON: dict[str, dict[str, list[str]]] = {
    tool_name: {"allowed_decisions": ["approve", "reject"]}
    for tool_name in SENSITIVE_BACKEND_TOOLS
}


class HumanInLoopMiddleware(HumanInTheLoopMiddleware):
    """暂停指定工具调用，等待人工批准或拒绝。"""

    def __init__(
        self,
        interrupt_on,
        *,
        description_prefix: str = "当前工具执行需要人工审批",
    ) -> None:
        super().__init__(
            interrupt_on=interrupt_on,
            description_prefix=description_prefix,
        )


def create_human_in_loop_middleware(
    approve_mode: str = "always_trust",
) -> HumanInLoopMiddleware | None:
    if approve_mode == "always_trust":
        return None
    return HumanInLoopMiddleware(interrupt_on=TOOL_APPROVAL_INTERRUPT_ON)
