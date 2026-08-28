# Archived Implementation Plan: Run Cancellation

计划版本：v0.1.0

归档状态：已完成并被后续版本替代。

### 1. Flow

1. `agent_router` 保持 cancel API。
2. `request_cancel_agent_run` 标记 run 与 direct child run 为
   `cancel_requested`。
3. 写 Redis cancel key 并发布 run_id 到 `run:cancel` 频道。
4. Worker `_cancellable_stream` 监听取消信号，抛
   `AgentRunCancelRequested`。
5. catch 后调用 `_finalize_run(status="cancelled")` 并清理信号。

### 2. Mapping

- `server/service/agent_run_service.py`: `request_cancel_agent_run`
- `server/service/arq_queue_servcie.py`: `publish_agent_run_cancel_signal`,
  `wait_agent_run_cancel_signal`, `clear_agent_run_cancel_signal`
- `server/worker.py`: `_cancellable_stream`, `AgentRunCancelRequested`,
  `_finalize_run`
- `src/database/repositories/agent_run_repository.py`: `request_cancel`,
  `set_agent_terminal`

### 3. Failure Handling

- 运行结束前取消 -> `cancelled`
- 运行结束后才到达取消 -> 响应 idempotent，保留最终终态
- Redis pub/sub 中断 -> 在 `has_agent_run_cancel_signal` 下次轮询兜底

