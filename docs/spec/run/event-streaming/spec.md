# Run Event Streaming Spec

## 1. Context

Agent Run 的运行事件先写入 Redis Stream，再由 SSE 读取并暴露给客户端。Redis
事件封装、Run 级读取编排和 SSE 传输格式属于三个不同职责，不能在
`AgentRunService` 中重复构造同一事件。

## 2. Contracts

### 2.1 Redis Stream envelope

- Stream Key：`run:events:{run_id}`
- `server/service/arq_queue_servcie.py` 是 envelope 构造和 Redis JSON 序列化的唯一所有者。
- Redis 中保存的事件结构为：

```json
{
  "run_id": "<uuid>",
  "event_type": "status|messages|values|agent_execute_event|end",
  "thread_id": "<thread-id>",
  "payload": {},
  "created_at": "<ISO8601>"
}
```

`payload` 是对应 `event_type` 的事件体，可以来自 Agent 输出投影，也可以来自
Worker 生命周期。它描述 envelope 中的位置和职责，不描述生产者；不得反向覆盖
envelope 的 `run_id`、`event_type`、`thread_id` 或 `created_at`。

### 2.2 SSE public contract

SSE 继续保持现有扁平响应，不把 Redis 内部 envelope 直接暴露给前端：

```text
id: <redis-stream-id>
event: end
data: {"scope":"agent_run","type":"end","run_id":"<uuid>","thread_id":"<thread-id>","status":"completed","created_at":"<ISO8601>"}

```

终态事件的最小约束为 `type=end`，且 `status` 只能是 `completed`、`failed`
或 `cancelled`。

## 3. Requirements

### RUN-ES-001 Redis 事件封装唯一所有者

Worker 的可观测事件统一通过 `write_agent_run_stream_event` 写入 Stream；
`arq_queue_servcie.py` 使用现有 builder 构造完整 envelope。
`agent_run_service.py` 不得再次定义或调用自己的 Agent Run event builder。

### RUN-ES-002 Run 级读取编排

`AgentRunService` 可以为 Run 状态查询、子 Agent 进度和 SSE 读取调用
`arq_queue_servcie.py` 的 Stream 读取方法，但不负责消息封装或 Redis 序列化。

### RUN-ES-003 SSE 格式化边界

`server/utils/agent_run_utils.py` 只负责把已经构造好的 Redis envelope 格式化为
SSE frame。它不得访问数据库、Redis 或修改 Run 生命周期。

### RUN-ES-004 终态兜底

若 Redis Stream 尚未创建、已经过期或缺失终态事件，
`stream_agent_run_events` 按 PostgreSQL 中的 Run 终态生成只用于当前 SSE
响应的兜底事件。兜底事件仍复用队列服务的 envelope builder，不写回 Redis。

### RUN-ES-005 Worker 写入语义

`server/worker.py` 通过 `write_stream_event` 写普通事件，通过
`write_end_stream_event` 写 `event_type="end"` 的终态事件。两个方法都是对
`write_agent_run_stream_event` 的薄包装：普通方法原样转发事件参数，终态方法
只固定事件类型并复用普通方法，不增加状态更新、任务停止或资源清理行为。
`write_end_stream_event` 只由 `_finalize_run` 在终态落库实际发生后调用。
三个 writer 对事件体统一使用参数名 `payload`，且
`write_end_stream_event` 必须把收到的 payload 写入 end envelope，不能只写空的
停止标记。

## 4. Acceptance Criteria

- `agent_run_service.py` 不再包含 Agent Run event builder 或事件发布包装。
- Redis 事件只由 `arq_queue_servcie.py` 构造并序列化。
- SSE formatter 位于 `server/utils/agent_run_utils.py`，且保持当前前端的扁平事件契约。
- SSE 按 Redis Stream ID 顺序读取，并在 `event_type=end` 时结束。
- 子 Agent 进度从 envelope 的 `payload` 读取 `status` 和 `error`。
- 数据库终态兜底不向 Redis Stream 重复写入事件。
- Worker 普通写入和终态写入分别使用两个语义明确的薄包装。
- 队列 writer、Worker 普通 writer 和 Worker end writer 对事件体统一使用
  `payload` 参数名和定义。
