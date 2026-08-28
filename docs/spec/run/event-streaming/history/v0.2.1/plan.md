# Archived Implementation Plan: Run Event Streaming

计划版本：v0.2.1

归档状态：已完成并被后续版本替代。

### Implementation Steps

1. 复用 `server/service/arq_queue_servcie.py:build_agent_chunk_envolope` 作为唯一
   envelope builder；`write_agent_run_stream_event` 继续负责 JSON 序列化和 Redis
   Stream 写入，不新增事件类或第二个 builder。
2. 在 `server/service/agent_run_service.py` 删除无调用的
   `publish_agent_run_event` 和旧 `_build_agent_run_event`。
3. 保留 `read_agent_run_events`、`read_subagent_progress` 和
   `stream_agent_run_events` 的 Run 级编排；读取逻辑适配
   `event_type + payload` envelope，终止判断改用 `event_type=end`。
4. 新增 `server/utils/agent_run_utils.py:format_agent_run_sse`，仅完成 Redis
   envelope 到现有扁平 SSE frame 的转换。
5. `stream_agent_run_events` 的数据库终态兜底调用队列服务 builder，再调用
   SSE formatter；不在 AgentRunService 内手写 envelope，也不写回 Redis。
6. 在 `server/worker.py` 新增两个薄包装：普通事件统一调用
   `write_stream_event`，终态事件统一调用 `write_end_stream_event`。后者只固定
   `event_type="end"` 并复用前者，不承担数据库终态、协程停止、缓冲刷新、取消
   信号清理或异常转换。
7. Worker 现有普通事件写入点改为调用 `write_stream_event`；
   `_finalize_run` 在数据库终态确实发生变化后调用 `write_end_stream_event`，
   其他调用点不直接写 `event_type="end"`。
8. 更新现有测试和 `AGENTS.md` 的当前职责说明，不修改前端契约、Redis key、
   TTL 或队列服务公开契约。

### Core Examples

#### Redis 写入

目标：`server/service/arq_queue_servcie.py:write_agent_run_stream_event`

```python
await write_agent_run_stream_event(
    run_id,
    "status",
    {"status": "running"},
    thread_id,
    ttl_seconds=RUN_REDIS_TTL_SECONDS,
)
```

该方法内部调用现有 `build_agent_chunk_envolope`；调用方不预先构造 envelope。

#### Worker 写入包装

目标：`server/worker.py:write_stream_event`、
`server/worker.py:write_end_stream_event`

```python
async def write_stream_event(
    run_id: str,
    event_type: str,
    event: dict[str, Any],
    thread_id: str | None = None,
) -> str:
    return await write_agent_run_stream_event(
        run_id,
        event_type,
        event,
        thread_id,
        ttl_seconds=RUN_REDIS_TTL_SECONDS,
    )


async def write_end_stream_event(
    run_id: str,
    event: dict[str, Any],
    thread_id: str | None = None,
) -> str:
    return await write_stream_event(run_id, "end", event, thread_id)
```

两个方法只表达 Worker 内部的普通写入与终态写入语义，不增加其他行为。

#### SSE 格式化

目标：`server/utils/agent_run_utils.py:format_agent_run_sse`

```python
frame = format_agent_run_sse(
    event_id,
    {
        "run_id": run_id,
        "event_type": "end",
        "thread_id": thread_id,
        "payload": {"status": "completed"},
        "created_at": created_at,
    },
)
```

输出仍为 `event: end`，且 `data` 保持前端当前使用的
`scope/type/run_id/thread_id/status/created_at` 扁平字段。

#### 数据库终态兜底

目标：`server/service/agent_run_service.py:stream_agent_run_events`

```python
envelope = build_agent_chunk_envolope(
    run_id=run_id,
    event_type="end",
    thread_id=thread_id,
    payload={"status": status, "error": error},
    created_at=datetime.now(UTC).isoformat(),
)
yield format_agent_run_sse(after_id, envelope)
```

### Scope Limits

- 不新增 Event model、factory、protocol 或兼容层。
- 不修改 Redis key、TTL、SSE endpoint、前端 DTO 或 Run 生命周期。
- `write_stream_event` 不改变参数内容；`write_end_stream_event` 只固定
  `event_type="end"`。
- 两个 Worker 包装方法不负责停止 Agent 流或 Worker 任务；执行终止仍由现有
  控制流负责。

### Validation

- 运行 `test/test_agent_run_service.py` 与
  `test/test_worker_stream_event_smoother.py` 中的定向 `unittest`。
- 对变更的 service、utils、Worker 和测试文件运行 `compileall`。
- 运行 `git diff --check`。
- 只修复本次包装接入直接覆盖到的 Worker 未完成代码；其余既有 Worker 改动若
  阻塞验证则单独报告。

