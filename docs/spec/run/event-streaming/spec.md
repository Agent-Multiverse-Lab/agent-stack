# Run Event Streaming Spec

## 1. Context

SSE 读取依赖 Redis Stream，支持边读边写与断线重连。终态必须有明确定义。

## 2. Contract

- Stream Key：`run:events:{run_id}`
- Event envelope：

```text
{
  "scope": "agent_run",
  "run_id": "<uuid>",
  "type": "status|messages|values|agent_execute_event|end",
  "created_at": "ISO8601",
  ...type-specific fields
}
```

- End event 最小约束：`{"type":"end","status":"completed|failed|cancelled"}`

## 3. Requirements

### RUN-ES-001
Worker 所有可观测事件统一通过 `write_agent_run_stream_event` 写入 Stream。

### RUN-ES-002
客户端 SSE 按 cursor 读取 event-id，直到 `type=end` 结束。

### RUN-ES-003
若 worker 崩溃导致 stream 未写入末端，服务端在补偿路径按 DB 状态补齐 `end` 事件。

## 4. Example

```python
await write_agent_run_stream_event(
    run_id,
    {"type": "status", "status": "running", "thread_id": thread_id},
    ttl_seconds=RUN_REDIS_TTL_SECONDS,
)
await publish_agent_run_event(run_id, {"type": "end", "status": "cancelled", "thread_id": thread_id})
```

## 5. Acceptance Criteria

- 事件有序追加，不丢失 type/end。
- 同一 run 的 SSE 连接可重连并继续按最后 id 拉取。
- 客户端收到 `type=end` 后关闭流。
