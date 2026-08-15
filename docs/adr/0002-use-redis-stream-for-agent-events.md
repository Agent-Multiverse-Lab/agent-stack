# ADR-0002: 使用 Redis Stream 作为 AgentRun 事件总线

## Status
Accepted

## Context
run 执行需要持续流式消费；HTTP SSE 连接需要重连友好的时间有序事件源，且避免数据库轮询压力。

## Decision
使用 Redis Stream 作为事件主通道：
- 写入事件键：`run:events:{run_id}`
- 事件字段统一写入 `event` JSON（含 `scope/run_id/created_at/type`）
- 终止事件始终是 `type=end` 且带 `status`

## Consequences
- SSE 可通过 `XREAD` 按 cursor 读取事件。
- 事件可保留 TTL，异常恢复时仍可重放最近事件。
- 数据库只负责状态真相，Stream 不作为状态源。

## Alternatives Considered
- 数据库轮询：带来更高延迟与高频读放大。
- WebSocket：对重连、网关兼容性更复杂。

## References
- [run-system.md](../architecture/run-system.md)
- [doc/spec/run/event-streaming/spec.md](../spec/run/event-streaming/spec.md)
