# 实施切片：运行时 Steer 优雅停机与晋升

## 1. 单一状态判断原则

- 不向 ARQ 队列或 Redis 写入额外的 `run:steer:{run_id}` 信号。
- PostgreSQL `AgentRunRequest`（利用部分索引 `ix_agent_run_request_thread_queued`）是等待区与 `steer` 状态的唯一事实来源。
- 优势：若用户在当前 Turn 完成前通过 `DELETE /api/agent/runs/requests/{request_id}` 撤销了 `steer` 请求，状态自动消除，不存在 Redis 信号与数据库不同步问题。

## 2. Turn 边界优雅停机（`before_model` 跳 `END`）

目标：`src/agents/middlewares/steer_stop_middleware.py`、`src/agents/buildin/leader/agent.py`。

- 定义 `SteerStopMiddleware(AgentMiddleware)`，实现异步 `before_model` 并声明 `@hook_config(can_jump_to=["end"])`：
  - 通过 `runtime.context.thread_id` 查询 `AgentRunRequestRepository.has_queued_steer_for_thread(thread_id)`，判断当前会话下是否存在 `status == "queued"` 且 `dispatch_policy == "steer"` 的请求。
  - 若存在，返回 `{"jump_to": "end"}`。
- 执行效果：
  - 若当前在 `model` 生成中：等待本轮模型响应结束；若模型未调用工具，图自然走向 `END`；若模型发起了 `tool_calls`，则等本批次 `tools` 全部执行完毕并提交 `AsyncPostgresSaver` checkpoint 后，在进入下一轮 `model` 前的 `before_model` 跳至 `after_agent -> END`。
  - 保证 `AIMessage(tool_calls)` 与 `ToolMessage` 在 checkpoint 与数据库中始终成对闭合。

## 3. Worker 终态收敛与晋升调度

目标：`server/worker.py`、`server/service/agent_run_service.py`。

- **终态区分**：当 `stream_agent_response` 正常结束流退出时，Worker（或 `thread_service`）结合 `has_queued_steer_for_thread(thread_id)`（或 `SteerStopMiddleware` 在本次执行中触发的转向标记）判断退出原因：
  - 若因存在 `queued` `steer` 请求跳 `END` 退出，将当前 Run 收敛为 `cancelled`（并记录 `stop_reason="steered"`），发布 `end` 事件。
  - 若期间用户触发了显式硬取消，仍由 `_cancellable_stream` 走 `CancelledError` 收敛为 `cancelled`。
- **晋升钩子 `dispatch_next_queued_request(thread_id)`**：
  - 在 `process_agent_run` 完成终态提交（`completed` / `failed` / `cancelled`，不含 `interrupted`）并释放 `AgentRunExecution` 之后调用。
  - 在 `reconcile_expired_run_leases` 将过期 Run 收敛为 `failed (LeaseExpired)` 之后同样调用，防止 Worker 宕机后等待区请求饥饿。
  - 函数内部锁 `Conversation(thread_id)`，确认无活跃 Run 且无 `interrupted` 交互后，弹出队首 `AgentRunRequest(status="queued")`、升级关联 `Message`、创建 `AgentRun(pending)`、提交事务并调用原生的 `enqueue_agent_run(run.id)`。
