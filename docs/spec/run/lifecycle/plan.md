# Implementation Plan: Run Lifecycle

## 1. Implementation Steps

1. 将 run 执行结束统一收口到 `server/worker.py:_finalize_run`。
2. `_finalize_run` 先做 `set_run_terminal`，再写 terminal 事件到 Redis Stream。
3. 保留 `completed` 路径通过 `set_run_terminal(status="completed", conversation_id, content)` 写入结果消息。
4. `failed` 和 `cancelled` 路径仅写 `status/error/error_type` 到 DB 与事件。

## 2. Mapping

- `server/worker.py`: `_finalize_run`, `_get_agent_run`, `process_agent_run`
- `server/service/agent_run_service.py`: `publish_agent_run_event`, `stream_agent_run_events`
- `src/database/repositories/agent_run_repository.py`: `set_agent_terminal`

## 3. Interface Changes

- `server/worker.py` `set_run_terminal` 增强 `conversation_id/content` 的完成态校验，保持已存在参数名不变。
- `stream_agent_run_events` 在 DB 已终态时补齐 end 兜底事件（保持幂等）。

## 4. Validation

- 运行 `test/test_worker_stream_event_smoother.py` 与 `test/test_agent_run_service.py`（有则执行）
- 手工验证：同一 run 重复 finalize 时 `status` 不回退
