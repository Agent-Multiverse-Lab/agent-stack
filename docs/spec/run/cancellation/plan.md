# Implementation Plan: Run Cancellation

计划版本：`v0.3.0`

本文件只承载当前版本；已实施计划位于 `history/<version>/plan.md`。当前版本在实施完成前
只做同版本修订，不产生新的历史版本。

## 1. Implementation Steps

1. `server/worker.py:process_agent_run` 初次加载 Run 或执行前状态检查发现
   `cancel_requested` 时，直接调用 `set_run_terminal(status="cancelled")`，不调用
   `_finalize_run` 或写 Redis `end`。
2. `process_agent_run` 进入 Agent Stream 消费循环前发生的停止，直接调用现有
   `set_run_terminal` 提交数据库
   对应原因的终态，不调用 `_finalize_run` 或 `write_end_stream_event`；取消请求
   写 `cancelled`，不清理 cancel key，执行准备错误按
   [`RUN-LC-005`](../lifecycle/spec.md) 写 `failed + error/error_type`，Run 不存在或
   已有终态则直接返回。
3. 进入 Agent Stream 消费循环后的正常完成或失败继续沿用现有终态路径；取消不调用
   `_finalize_run`，而是先释放 Smoother，再显式提交 PostgreSQL 终态，并以返回的实际
   状态写入 `end`。Stream 前取消仍只写数据库，不写孤立 `end`。
4. `server/worker.py:_cancellable_stream` 在取消等待任务先完成时，主动取消并
   `await` 当前 `anext()` 任务，以 `try/except asyncio.CancelledError` 显式接住
   该子任务的取消结果，然后直接抛出 `asyncio.CancelledError`。删除
   `AgentRunCancelRequested`，不保留第二套 Worker 取消异常。
5. `server/worker.py:process_agent_run` 显式捕获 `asyncio.CancelledError` 并重新
   调用一次 `StreamEventSmoother.release()`，然后直接调用
   `set_run_terminal(status="cancelled")`，接收 `agent_status, changed`。仅当
   `changed=True` 且 `agent_status == "cancelled"` 时调用
   `write_end_stream_event`；最后返回数据库结果。不预读 Run，不遍历
   `chunk_buckets`，不调用 `_finalize_run` 或 `clear_agent_run_cancel_signal`。
6. 遵循 [`RUN-ES-004`](../event-streaming/spec.md) 的 PostgreSQL 驱动终止
   规则：`stream_agent_run_events` 先读取 Run 最新状态；Redis `end` 只唤醒
   状态重查。数据库已终态时先排空未消费 chunk，再根据数据库生成唯一 SSE
   `end`，且不写回 Redis。
7. 更新现有 Worker 定向测试，覆盖 Agent Stream 前停止不写 Redis `end`、
   Agent Stream 内取消按 release、数据库终态、实际返回状态写 `end` 的顺序收敛，
   以及 `changed=False` 时不重复写 `end`，并同步 `AGENTS.md` 的当前运行模型。

## 2. Ownership

- `process_agent_run`：通过现有 Agent Stream 消费循环的控制流边界，选择数据库
  终态写入或 Stream 终态收敛，不新增状态标记。
- `set_run_terminal`：只提交 PostgreSQL 终态和既有终态数据，不产生 Redis
  Stream 事件。
- `_finalize_run`：不参与用户取消路径；其他终态行为保持现有职责。
- `_cancellable_stream`：取消当前流消费子任务并直接传播
  `asyncio.CancelledError`，不定义 Run 生命周期状态。
- `process_agent_run`：捕获 `asyncio.CancelledError` 后以 PostgreSQL
  终态写入为唯一状态判断边界；调用一次 Smoother `release()`，再通过
  `set_run_terminal` 收敛数据库状态，并以实际返回状态决定是否写 `end`。
- `StreamEventSmoother.release()`：无参数时释放当前 Smoother 的全部待发送 bucket，
  不要求调用方访问 `chunk_buckets`。
- `stream_agent_run_events`：以 PostgreSQL Run 状态决定是否结束，终态时排空
  未消费 chunk，再生成唯一 SSE `end`，不回写 Redis。

## 3. Core Examples

### 3.1 初始状态检查

目标：`server/worker.py:process_agent_run`

```python
initial_status = str(agent_run_event.agent_status)
if initial_status in {"completed", "failed", "cancelled"}:
    return
if initial_status == "cancel_requested":
    return await set_run_terminal(run_id, status="cancelled")
```

这里直接收敛 PostgreSQL 取消终态，但不创建尚无前序数据的 Redis Stream。

### 3.2 Agent Stream 前取消

目标：`server/worker.py:process_agent_run`

```python
await set_run_terminal(
    run_id,
    status="cancelled",
)
return
```

该分支不消费 `set_run_terminal` 的返回值，也不调用 `_finalize_run`，因此不会创建
只有终态事件的 Redis Stream。它只覆盖 `cancel_requested`；其他 Agent Stream
前退出按 [`RUN-LC-005`](../lifecycle/spec.md) 保留各自的不存在、既有终态或
`failed` 语义。

### 3.3 Agent Stream 内停止

目标：`server/worker.py:process_agent_run`

```python
async for chunk in _cancellable_stream(
    stream_thread_events,
    run_context=run_context,
):
    ...
```

取消退出不新增 `has_agent_chunk` 或其他状态标记。Stream 前取消不写 `end`；进入
Stream 后捕获的取消显式写终态事件，但不调用 `_finalize_run`。

### 3.4 显式收敛流消费任务取消

目标：`server/worker.py:_cancellable_stream`

```python
stream_task.cancel()
try:
    await stream_task
except asyncio.CancelledError:
    pass

await cancel_task
raise asyncio.CancelledError()
```

目标：`server/worker.py:process_agent_run`

```python
except asyncio.CancelledError:
    await stream_event_smoother.release()
    agent_status, changed = await set_run_terminal(
        run_id,
        status="cancelled",
    )
    if changed and agent_status == "cancelled":
        await write_end_stream_event(
            run_id,
            {"status": agent_status},
            str(thread_id),
        )
    return agent_status, changed
```

`asyncio.CancelledError` 是唯一的进程内取消控制流。是否写入 `cancelled` 只由
`set_run_terminal` 内部读取并锁定的 PostgreSQL 状态决定，Redis 信号和异常本身都
不定义 Run 状态。Redis `end` 使用 `set_run_terminal` 返回的实际状态，并由
`changed` 防止重复终态事件。

## 4. Failure Handling

- 初次加载为 `cancel_requested`：不提前返回，继续到执行前状态检查点。
- 执行前检查仍为 `cancel_requested`：提交 `cancelled`，清理取消 key，不写 Redis
  `end`。
- Agent Stream 前取消：提交 `cancelled` 并清理 cancel key，不写 Redis `end`。
- Agent Stream 前准备错误：提交 `failed + error/error_type`，不写 Redis `end`。
- Run 不存在或已有终态：不伪造新的 `cancelled/failed`，直接返回。
- Redis `end` 到达：只唤醒 SSE 重新查询 PostgreSQL，不直接决定 Run 终态。
- PostgreSQL 已终态：SSE 排空未消费 chunk 后生成唯一公共 `end`，不向 Redis
  补写。
- Agent Stream 内取消：直接调用一次 `StreamEventSmoother.release()`，再通过
  `set_run_terminal` 写入 `cancelled`；仅由实际 `agent_status` 与 `changed` 决定是否
  写入 Redis `end`。
- PostgreSQL 当前状态与终态防竞态由 `set_run_terminal` 的仓储调用负责，不在
  `process_agent_run` 中增加一次无锁预读。
- 流消费子任务取消：显式捕获子任务的 `asyncio.CancelledError`，等待取消监听结果
  后继续以 `asyncio.CancelledError` 退出流消费。
- `process_agent_run` 捕获取消：重新读取 PostgreSQL；状态为 `cancel_requested` 才
  写入 `cancelled`，其他状态重新抛出 `asyncio.CancelledError`。

## 5. Scope Limits

- 不新增取消结算 Service、Context、状态值、数据表或字段。
- 不修改 cancel API、Redis key/channel、SSE DTO 或前端行为。
- 不改变 `AgentRunContext` 或 Redis writer 的现有职责；`_cancellable_stream` 只改变
  已有流消费任务的取消等待方式。
- 不新增或保留 `AgentRunCancelRequested` 等 Worker 自定义取消异常。
- 不新增“是否已产生事件”标志；Stream 内取消不调用 `_finalize_run`，而是显式使用
  数据库终态结果写 `end`。
- 不从 `process_agent_run` 读取或遍历 `StreamEventSmoother.chunk_buckets`。
- 取消路径不调用 `clear_agent_run_cancel_signal`。
- 不新增 Agent chunk 状态标记，不处理与现有循环边界无关的 Worker 重构。

## 6. Validation

- 运行 `test/test_worker_stream_event_smoother.py` 的定向 `unittest`。
- 对 `server/worker.py` 与对应测试运行 `compileall`。
- 运行 `git diff --check`。
