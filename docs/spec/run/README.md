# Run Domain

Run Domain 处理所有 `AgentRun` 的生命周期与可观察性。

## 子域

- `lifecycle/`：状态流转、终态落库、异常映射
- `cancellation/`：取消请求、信号、worker 中断
- `event-streaming/`：Redis Stream + SSE 的事件契约

## 关系

1. `lifecycle` 定义终态语义与 DB 规则  
2. `cancellation` 提供中断行为并映射到终态  
3. `event-streaming` 提供终态可见性与客户端消费协议
