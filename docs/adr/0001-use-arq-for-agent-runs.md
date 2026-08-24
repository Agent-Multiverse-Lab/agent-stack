# ADR-0001: Run 执行必须通过 ARQ Worker

## Status
Accepted

## Context
`AgentRun` 是异步长耗时任务，不应在 FastAPI 请求线程直接执行；需要独立进程消费、可重试、可并发。

## Decision
Run 执行统一走 `ARQ`。  
流程为：`POST /api/agent/runs` -> `enqueue_job("process_agent_run", run_id, _job_id="run:{run_id}")` -> Worker 执行 `process_agent_run`。

## Consequences
- API 延迟固定且可控，不受 run 执行时长影响。
- 支持多 worker 并发消费。
- Cancel、事件监听与重试策略统一放入 worker 协作层。
- 运行端点与 API 端点解耦，职责清晰。

## References
- [run-system.md](../architecture/run-system.md)
- [docs/spec/run/README.md](../spec/run/README.md)
