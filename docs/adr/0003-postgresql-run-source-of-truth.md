# ADR-0003: PostgreSQL 是 AgentRun 的状态真相

## Status
Accepted

## Context
run 状态需要可重试、可审计、可恢复。Redis/Stream 只适合运行时通信，缺少可持久化语义。

## Decision
`AgentRun.agent_status`、`error`、`error_type`、`finished_at` 等终态字段全部以 PostgreSQL 为主状态源。

## Consequences
- 终态判断统一从 DB 查询，避免读取偏差。
- 取消/失败后的恢复行为只要重查 DB 即可决策。
- `agent_run` SSE 最终层若发现 DB 仍处于终态则补齐 terminal event（兜底一致性）。

## References
- [persistence-system.md](../architecture/persistence-system.md)
- [docs/spec/run/lifecycle/spec.md](../spec/run/lifecycle/spec.md)
