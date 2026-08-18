# Implementation Plan: Run Cancellation

计划版本：`v0.3.0`

当前版本位于正文；已实施的旧计划保留在文末“历史版本”中。当前版本在实施完成
前只做同版本修订，不产生新的历史版本。

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

## 7. 历史版本

以下快照是已经实施的旧计划，不属于当前执行范围。

<details>
<summary>计划版本：v0.2.0</summary>

## 1. Implementation Steps

1. 在 `server/worker.py` 新增 `AgentRunContext`，每个执行中的 Run 只持有一个
   私有 `asyncio.Event` 和一个 Redis 取消监听任务。
2. `AgentRunContext.start()` 显式创建监听任务，`close()` 显式取消并等待监听
   任务；`wait_cancel_signal()` 封装 `_cancel_event.wait()`，监听异常继续向
   等待方传播。
3. 删除独立的 `wait_cancel_event(run_id, event)`；`_cancellable_stream` 改为
   接收 `AgentRunContext`，竞争 `anext(stream)` 与
   `run_context.wait_cancel_signal()`，不再自行创建 Event 或 Redis listener。
4. `process_agent_run` 在 `set_run_running()` 确认 Run 已进入 `running` 后
   创建 Context 并调用 `start()`；整个活动执行放在 `try/finally` 中，
   `finally` 调用 `close()`。
5. 保留流结束后的 Redis cancel key 检查，作为完成态写入前的同步兜底。Context
   负责活动期低延迟唤醒，不替代 PostgreSQL 终态竞争或 Redis key 兜底。
6. 在现有 `test/test_worker_stream_event_smoother.py` 增加最小异步测试，验证
   `wait_cancel_signal()` 能中断流，并验证 `close()` 会回收仍在等待的监听
   任务。
7. 更新 `AGENTS.md` 的当前 Worker 取消运行模型，以及“未实施计划不升级版本”
   的计划维护规则。

## 2. Ownership

- `AgentRunContext`：当前 Worker 进程内、当前 Run 的取消 Event 与监听任务。
- `arq_queue_servcie.py`：Redis cancel key 和 Pub/Sub 的具体等待、检查与清理。
- `AgentRunRepository`：持久化 `cancel_requested/cancelled` 状态。
- `_cancellable_stream`：竞争 Agent 流下一项与 Context 取消信号，不拥有 Run
  生命周期。

`wait_cancel_signal()` 只表示“等待取消信号到达”。它不表示 Agent 已经停止，
也不表示 PostgreSQL 已经写成 `cancelled`，因此不命名为
`wait_agent_cancel()`。

## 3. Core Examples

### 3.1 Run Context

目标：`server/worker.py:AgentRunContext`

```python
@dataclass
class AgentRunContext:
    run_id: str
    _cancel_event: asyncio.Event = field(
        default_factory=asyncio.Event,
        init=False,
    )
    _cancel_listener_task: asyncio.Task[None] | None = field(
        default=None,
        init=False,
    )

    def start(self) -> None:
        self._cancel_listener_task = asyncio.create_task(
            self._watch_cancel_signal()
        )

    async def wait_cancel_signal(self) -> None:
        await self._cancel_event.wait()
        if self._cancel_listener_task is not None:
            await self._cancel_listener_task

    async def close(self) -> None:
        task = self._cancel_listener_task
        if task is None:
            return
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
```

`_watch_cancel_signal()` 调用现有
`wait_agent_run_cancel_signal(run_id)`，并在 `finally` 中设置
`_cancel_event`。Context 不持有 Redis 客户端或持久化 Run 状态。

### 3.2 可取消流

目标：`server/worker.py:_cancellable_stream`

```python
cancel_task = asyncio.create_task(run_context.wait_cancel_signal())
done, _ = await asyncio.wait(
    {stream_task, cancel_task},
    return_when=asyncio.FIRST_COMPLETED,
)
if cancel_task in done:
    stream_task.cancel()
    await asyncio.gather(stream_task, return_exceptions=True)
    await cancel_task
    raise AgentRunCancelRequested(run_context.run_id)
```

`_cancellable_stream` 的 `finally` 只回收 `stream_task` 与
`cancel_task`；Context 持有的 Redis listener 在整个 Run 活动窗口内继续存在。

### 3.3 Run 生命周期

目标：`server/worker.py:process_agent_run`

```python
running_run = await set_run_running(run_id)
# 保留 cancel_requested 与终态检查。

run_context = AgentRunContext(run_id)
run_context.start()
try:
    async for chunk in _cancellable_stream(
        stream_thread_events,
        run_context=run_context,
    ):
        ...
finally:
    await run_context.close()
```

Context 的启动点位于 Run 确认 `running` 之后、发布 running 事件之前；退出点
位于正常完成、失败或取消的终态处理之后。更早到达的取消继续由初始状态检查和
`set_run_running()` 的锁内状态检查处理。

## 4. Failure Handling

- Redis cancel key 已存在：Context listener 首次检查立即设置 Event。
- Pub/Sub 在订阅前出现信号：现有 key 重查覆盖该竞态。
- Redis listener 异常：设置 Event 唤醒等待方，`wait_cancel_signal()` 重新
  抛出原异常，由 `process_agent_run` 的失败路径处理。
- Agent 流先结束：`_cancellable_stream` 回收自己的等待任务，Context listener
  继续存活到 Run 终态处理完成。
- Run 正常结束、提前返回、异常或 Worker 任务取消：`finally` 中的 `close()`
  取消并等待 listener，避免后台任务泄漏。

## 5. Scope Limits

- 不新增独立 Context 文件、协议、工厂、注册表或第三方依赖。
- 不把数据库状态、Agent 消息、Stream Event、Redis 客户端或缓冲器放进
  `AgentRunContext`。
- 不修改 `set_run_running()`、cancel API、Redis key/channel、Run 状态值或
  SSE 契约。
- 不把 ARQ 的共享 `ctx` 用作单个 Run Context；每次
  `process_agent_run` 调用只创建自己的局部 Context。

## 6. Validation

- 运行 `test/test_worker_stream_event_smoother.py` 的定向 `unittest`。
- 对 `server/worker.py` 与对应测试运行 `compileall`。
- 运行 `git diff --check`。

## 7. 历史版本

以下快照是已经实施的旧计划，不属于当前执行范围。

<details>
<summary>计划版本：v0.1.0</summary>

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

</details>

</details>
