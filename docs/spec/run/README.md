# Run Domain

Run Domain 处理所有 `AgentRun` 的生命周期与可观察性。

## 子域

- `lifecycle/`：状态流转、终态落库、异常映射
- `cancellation/`：取消请求、信号、worker 中断
- `event-streaming/`：Redis Stream + SSE 的事件契约
- `message-persistence/`：LangGraph Message 到 PostgreSQL Message/ToolCall 的持久化
- `interrupt-resume/`：工具审批打断、父子 Run 与 checkpoint 恢复

## 关系

1. `lifecycle` 定义终态语义与 DB 规则  
2. `cancellation` 提供中断行为并映射到终态  
3. `message-persistence` 在正常终态前持久化 Agent 输出和工具结果
4. `event-streaming` 提供终态可见性与客户端消费协议
5. `interrupt-resume` 扩展 `interrupted` 终态，并创建新的 Resume Run 从 checkpoint 继续
