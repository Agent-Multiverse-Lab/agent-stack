# Architecture Decision Record（ADR）

本目录沉淀关键架构决策，按时间顺序维护关键技术分歧与约束。

- [0001-use-arq-for-agent-runs.md](0001-use-arq-for-agent-runs.md)
  - 采用 ARQ 作为 Agent Run 的后台任务分发基础。
- [0002-use-redis-stream-for-agent-events.md](0002-use-redis-stream-for-agent-events.md)
  - 使用 Redis Stream 承载 run 事件流和可观测输出来支撑 SSE。
- [0003-postgresql-run-source-of-truth.md](0003-postgresql-run-source-of-truth.md)
  - 明确 PostgreSQL 是运行状态真相来源，Redis 仅作运行时通道。
- [0004-separate-sandbox-service.md](0004-separate-sandbox-service.md)
  - 将沙箱能力与主服务分离，降低执行面影响。
