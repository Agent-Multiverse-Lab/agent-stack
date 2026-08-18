# Implementation Plan: Run Event Streaming

计划版本：`v0.3.0`

当前版本位于正文；已被替代的完整计划保留在文末“历史版本”中。

## 1. Implementation Steps

1. 调整 `server/service/agent_run_service.py:stream_agent_run_events`，每轮先重新
   查询 PostgreSQL 中的最新 `AgentRun.agent_status`，不复用连接建立时读取的
   Run 状态作为终态依据。
2. Run 未终态时继续读取和格式化普通 Redis 事件；Redis `event_type="end"`
   只结束本次等待并触发下一轮数据库状态重查，不直接输出公共 SSE `end`。
3. Run 已终态时，从当前 cursor 非阻塞排空 Redis 中尚未发送的普通事件；排空后
   使用数据库中的 `agent_status/error` 构造唯一公共 SSE `end` 并结束生成器。
4. Redis Stream 不存在或没有新事件时，读取必须在有限时间内返回，使 SSE 能够
   再次查询数据库；不新增 Redis key、数据库通知或后台轮询任务。
5. 保留 `server/worker.py:_finalize_run` 的顺序：flush Agent chunk、提交数据库
   终态，再写 Redis `end`。该 Redis `end` 只唤醒 SSE 状态重查。
6. Agent Stream 消费循环前停止只调用 `set_run_terminal`，不调用 `_finalize_run` 或
   创建 Redis Stream；SSE 仍通过同一 PostgreSQL 驱动流程生成公共 `end`。
7. 更新 `test/test_agent_run_service.py` 的定向测试，覆盖 Redis `end` 不直接结束、
   数据库终态前排空普通事件、无 Redis Stream 时根据数据库结束，并同步
   `AGENTS.md` 的当前事件与终态所有权。

## 2. Ownership

- PostgreSQL `AgentRun.agent_status`：Run 终态唯一事实来源。
- Redis Stream：普通事件的有序传输，以及已有事件流上的终态重查唤醒。
- `stream_agent_run_events`：重新读取数据库状态、排空 Redis 普通事件并生成公共
  SSE `end`。
- `format_agent_run_sse`：只格式化已经确定的 envelope，不查询数据库或 Redis。

## 3. Core Examples

### 3.1 数据库优先的 SSE 循环

目标：`server/service/agent_run_service.py:stream_agent_run_events`

```python
while True:
    run = await load_current_agent_run(run_id)
    terminal = str(run.agent_status) in AGENT_RUN_TERMINAL_STATUSES
    events = await read_agent_run_stream_events(
        run_id,
        after_id=after_id,
        block=not terminal,
    )

    for event_id, envelope in events:
        after_id = event_id
        if envelope["event_type"] == "end":
            continue
        yield format_agent_run_sse(event_id, envelope)

    if terminal and not events:
        yield format_agent_run_sse(
            after_id,
            build_terminal_envelope(run),
        )
        return
```

示例表达控制顺序；实现复用现有 repository、queue reader、builder 和 formatter，
不新增 `load_current_agent_run` 或 `build_terminal_envelope` 公共抽象。

### 3.2 Redis end 只负责唤醒

目标：`server/service/agent_run_service.py:stream_agent_run_events`

```python
if envelope["event_type"] == "end":
    continue  # 下一轮重新查询 PostgreSQL。
```

公共 SSE `end` 的 `status/error` 只取自下一轮读取到的数据库 Run。

### 3.3 无 Redis Stream 的执行前终态

目标：`server/worker.py:process_agent_run`、
`server/service/agent_run_service.py:stream_agent_run_events`

```python
await set_run_terminal(run_id, status="cancelled")
# Agent Stream 前不写 Redis end；SSE 的有限等待返回后重新查询数据库并生成公共 end。
```

## 4. Failure Handling

- Redis `end` 先于 SSE 的数据库查询到达：只唤醒重查，不直接结束。
- 数据库已终态但仍有未消费普通事件：先按 Stream ID 排空，再生成公共 `end`。
- Redis Stream 不存在或已过期：有限等待后重新查库，数据库终态即可结束。
- Redis `end` 写入失败：数据库终态仍能在下一次状态检查时结束 SSE。
- 数据库仍非终态：不得根据 Redis payload 中的 status 生成公共 `end`。

## 5. Scope Limits

- 不新增状态表、Redis key、数据库通知、后台任务或兼容路径。
- 不修改公开 SSE DTO、普通事件 envelope 或 Redis Stream cursor 语义。
- 不把数据库查询放入 `format_agent_run_sse` 或队列服务。
- 不调整 Agent chunk 内容、缓冲阈值或前端消费逻辑。

## 6. Validation

- 运行 `test/test_agent_run_service.py` 与
  `test/test_worker_stream_event_smoother.py` 中的定向 `unittest`。
- 对变更的 service、Worker 和测试文件运行 `compileall`。
- 运行 `git diff --check`。

## 7. 历史版本

以下快照仅用于保留计划演进记录，不属于当前执行范围。

<details>
<summary>计划版本：v0.2.2</summary>

## 1. Implementation Steps

1. 复用 `server/service/arq_queue_servcie.py:build_agent_chunk_envolope` 作为唯一
   envelope builder；`write_agent_run_stream_event` 的事件体参数统一命名为
   `payload`，继续负责 JSON 序列化和 Redis Stream 写入，不新增事件类或第二个
   builder。
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
   `event_type="end"` 并把同名 `payload` 原样传给前者，不承担数据库终态、协程
   停止、缓冲刷新、取消信号清理或异常转换。
7. Worker 现有普通事件写入点改为调用 `write_stream_event`；
   `_finalize_run` 在数据库终态确实发生变化后调用 `write_end_stream_event`，
   其他调用点不直接写 `event_type="end"`。
8. 更新现有测试和 `AGENTS.md` 的当前职责说明，不修改前端契约、Redis key、
   TTL 或队列服务公开契约。

## 2. Naming Contract

- `event_type`：Redis/SSE 的事件类别和路由名称。
- `payload`：当前 `event_type` 的事件体，可以是 Agent 输出的投影，也可以是
  Worker 产生的生命周期数据。
- `envelope`：由 `run_id`、`event_type`、`thread_id`、`payload` 和
  `created_at` 组成的完整 Redis 事件。
- `write_agent_run_stream_event`、`write_stream_event` 和
  `write_end_stream_event` 对同一事件体统一使用参数名 `payload`；不再在相邻层
  交替使用 `event`、`data` 或 `chunk` 指代它。

当前 Worker 的三个 Redis 写入点中：

1. `StreamEventSmoother.release` 写入 `messages`，payload 是 Agent chunk 列表；
2. `process_agent_run` 写入 `status/running`，payload 是 Worker 生命周期数据；
3. `map_stream_event` 产生的 payload 来自 Agent chunk 的事件投影。

因此 `payload` 描述的是 envelope 中的位置和职责，不描述数据生产者。

## 3. Core Examples

### 3.1 Redis 写入

目标：`server/service/arq_queue_servcie.py:write_agent_run_stream_event`

该方法签名中的事件体参数命名为 `payload`：

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

### 3.2 Worker 写入包装

目标：`server/worker.py:write_stream_event`、
`server/worker.py:write_end_stream_event`

```python
async def write_stream_event(
    run_id: str,
    event_type: str,
    payload: dict[str, Any],
    thread_id: str | None = None,
) -> str:
    return await write_agent_run_stream_event(
        run_id,
        event_type,
        payload,
        thread_id,
        ttl_seconds=RUN_REDIS_TTL_SECONDS,
    )


async def write_end_stream_event(
    run_id: str,
    payload: dict[str, Any],
    thread_id: str | None = None,
) -> str:

    return await write_stream_event(run_id, "end", payload, thread_id)
```

两个方法只表达 Worker 内部的普通写入与终态写入语义，不增加其他行为。

### 3.3 SSE 格式化

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

### 3.4 数据库终态兜底

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

## 4. Scope Limits

- 不新增 Event model、factory、protocol 或兼容层。
- 不修改 Redis key、TTL、SSE endpoint、前端 DTO 或 Run 生命周期。
- 三个 writer 的 `payload` 含义和参数名保持一致；`write_stream_event` 不改变其
  内容，`write_end_stream_event` 只固定 `event_type="end"`。
- 两个 Worker 包装方法不负责停止 Agent 流或 Worker 任务；执行终止仍由现有
  控制流负责。

## 5. Validation

- 运行 `test/test_agent_run_service.py` 与
  `test/test_worker_stream_event_smoother.py` 中的定向 `unittest`。
- 对变更的 service、utils、Worker 和测试文件运行 `compileall`。
- 运行 `git diff --check`。
- 只修复本次包装接入直接覆盖到的 Worker 未完成代码；其余既有 Worker 改动若
  阻塞验证则单独报告。

## 6. 历史版本

以下快照仅用于保留计划演进记录，不属于当前执行范围。

<details>
<summary>计划版本：v0.2.1</summary>

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

</details>

</details>

<details>
<summary>计划版本：v0.2.0</summary>

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

</details>

<details>
<summary>计划版本：v0.1.0</summary>

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
6. 更新现有测试和 `AGENTS.md` 的当前职责说明，不修改前端契约和 Worker
   执行流程。

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
- 不修改当前工作区中的 `server/worker.py` 未提交改动。

### Validation

- 运行 `test/test_agent_run_service.py` 中的定向 `unittest`。
- 对变更的 service、utils 和测试文件运行 `compileall`。
- 运行 `git diff --check`。
- 单独报告当前 `server/worker.py` 未完成改动导致的全量后端编译阻塞，不在本任务中代为修复。

</details>
