# Run Domain

Run Domain 处理 `AgentRun` 生命周期与可观察性。先选一个能力并读取其 `spec.md`；只有处理该能力
当前变更时，才继续读取同目录根部的 `plan.md` 和 `tasks.md`。

| Capability | 当前契约 | 职责 |
| --- | --- | --- |
| lifecycle | [spec.md](lifecycle/spec.md) | 状态流转、终态落库、异常映射 |
| cancellation | [spec.md](cancellation/spec.md) | 取消请求、信号与 Worker 中断 |
| event-streaming | [spec.md](event-streaming/spec.md) | Redis Stream 与 SSE 事件契约 |
| message-persistence | [spec.md](message-persistence/spec.md) | LangGraph Message 到 PostgreSQL Message/ToolCall 的持久化 |
| interrupt-resume | [spec.md](interrupt-resume/spec.md) | 工具审批打断、父子 Run 与 checkpoint 恢复 |

依赖关系：lifecycle 定义终态语义；cancellation 和 interrupt-resume 扩展停止路径；
message-persistence 在正常终态前保存输出；event-streaming 提供客户端可见性。
