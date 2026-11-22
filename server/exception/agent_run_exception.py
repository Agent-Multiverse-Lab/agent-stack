class AgentRunTimeOut(TimeoutError):
    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__(f"等待 Agent Run 结果超时：{run_id}")


class AgentRunConflictError(RuntimeError):
    """Agent Run 当前状态不允许执行请求。"""

    def __init__(self, message: str, *, run_id: str | None = None) -> None:
        super().__init__(message)
        self.run_id = run_id
