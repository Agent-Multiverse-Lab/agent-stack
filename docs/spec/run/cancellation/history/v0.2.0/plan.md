# Archived Implementation Plan: Run Cancellation

计划版本：v0.2.0

归档状态：已完成并被后续版本替代。

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

