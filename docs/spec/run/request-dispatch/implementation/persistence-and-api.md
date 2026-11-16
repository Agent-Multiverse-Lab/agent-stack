# 实施切片：持久化与 API 契约

## 1. 数据模型与迁移

目标：`src/database/models.py`、新 Alembic 迁移脚本。

- 在 `AgentRunRequest` 调整字段与索引：
  - 移除冗余的 `conversation_id` 列及其外键/索引（迁移需 `drop_column`）；`thread_id`（加索引，不建外键）逻辑关联 `Conversation.thread_id`，物理删除级联继续由 `trigger_message_id -> message.id (ON DELETE CASCADE)` 承接。
  - 新增 `dispatch_policy = Column(String(16), nullable=False, server_default="reject")`
  - 新增 `status = Column(String(16), nullable=False, server_default="dispatched")`
  - 新增 `queue_seq = Column(Integer, nullable=True)`
  - 新增部分索引 `ix_agent_run_request_thread_queued ON agent_run_request (thread_id, queue_seq) WHERE status = 'queued'`。
- 同步更新 `AgentRunRequestInput` 与 `AgentRunRequestRepository.create_request` 移除 `conversation_id` 参数；创建 `AgentRun` 时直接使用已锁定的 `Conversation.id`。
- 复用 `Message.status`（现有为 `"completed"`）：进入等待区时写入 `"queued"`，晋升时更新为 `"completed"` 并重分配当前会话的 `next_sequence()`。

## 2. Repository 职责

目标：`src/database/repositories/agent_run_request_repository.py`、`src/database/repositories/conversation_repository.py`。

- `AgentRunRequestRepository`：
  - `get_next_queue_seq(thread_id)`：在已持有的 `Conversation` 行锁内计算 `COALESCE(MAX(queue_seq), 0) + 1`。
  - `list_queued_for_thread(thread_id, uid)`：返回 `status == "queued"` 且归属该用户的请求，按 `queue_seq ASC` 排序并关联触发 `Message` 内容。
  - `has_queued_steer_for_thread(thread_id)`：判断当前会话是否存在 `status == "queued"` 且 `dispatch_policy == "steer"` 的请求，供运行时 `SteerStopMiddleware` 与 Worker 收尾阶段使用（利用部分索引 `ix_agent_run_request_thread_queued`）。
  - `pop_next_queued_for_thread(thread_id)`：按 `queue_seq ASC` 取队首（若存在 `dispatch_policy == "steer"` 且策略要求优先转向，优先取最新的 `steer` 或按 `queue_seq ASC`）。
  - `mark_dispatched(request_id)` / `cancel_queued_request(request_id, uid)`：仅在 `status == "queued"` 时执行状态迁移。
- `ConversationRepository`：
  - `get_messages_by_thread_id` 等历史消息读取方法过滤 `Message.status != "queued"`，防止等待区用户消息提前插到正在输出的回复前面。
  - `promote_queued_input_message(message_id, run_id)`：将 `status` 改为 `"completed"`、更新 `sequence` 并写入 `agent_run_id`。
  - `delete_queued_input_message(message_id)`：清理已撤销等待区请求的未绑定 `Message`。

## 3. Service 与 Router 路由

目标：`server/entities/agent.py`、`server/entities/thread.py`、`server/service/agent_run_service.py`、`server/router/agent_router.py`、`server/router/thread_router.py`。

- `create_agent_run_service`：
  - 在 `Conversation` 行锁内先判断 `request_id` 幂等与 `get_pending_interaction_run`。
  - 存在 `get_pending_interaction_run` 时，任何策略均不落盘，直接抛 409。
  - 若 `get_latest_active_for_thread` 存在活跃 Run：
    - `reject`：不落盘，直接抛 `AgentRunConflictError`（409）。
    - `queue`：落盘 `Message(status="queued")` + `AgentRunRequest(status="queued", dispatch_policy="queue")`，返回 HTTP 202（含 `queue_position`）。
    - `steer`：落盘 `Message(status="queued")` + `AgentRunRequest(status="queued", dispatch_policy="steer")`，提交事务后直接返回 HTTP 202（含 `steering_run_id`），无需额外写队列或 Redis 信号。
  - 会话空闲时，维持直接创建 `AgentRun(pending)` 与调用 `enqueue_agent_run(run.id)`。
- 新增 `DELETE /api/agent/runs/requests/{request_id}`：在 `Conversation` 行锁内校验状态，仅对 `queued` 执行移除；若已并发变为 `dispatched`，查询关联 `AgentRun.id` 并返回 409。
- `GET /api/chat/thread/{thread_id}` 在 `ThreadDetailResponse` 返回 `queued_requests`。
