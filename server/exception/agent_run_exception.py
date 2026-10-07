class AgentRunTimeOut(TimeoutError):
    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__(f"等待 Agent Run 结果超时：{run_id}")
