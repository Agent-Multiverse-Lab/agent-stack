# Run Cancellation Spec

## 1. Context

`cancel` 是用户可见的停止控制，目标是确保执行链条在可观测内快速停止，并最终落库为 `cancelled`。

## 2. Requirements

### RUN-CAN-001 终端统一
`cancel run` 必须触发：

- 当前 run 与直接子 run 标记为 `cancel_requested`
- 取消信号 `run:cancel:{run_id}`
- 通过 Pub/Sub 通知 worker

### RUN-CAN-002 幂等
同一 run 重复取消请求不应抛错，只返回当前可见状态。

### RUN-CAN-003 最终落库
Worker 感知取消后完成当前执行阶段的停止处理，再写入 `cancelled`（若仍处于可中断
态）。初次加载 Run 或执行前状态检查发现 `cancel_requested` 时，直接通过
`set_run_terminal` 写入 `cancelled`，不得创建 Redis `end`。

### RUN-CAN-004 统一终态
一旦 DB 状态变为 `completed/failed`，后续取消不能覆盖终态。

### RUN-CAN-005 Run 级取消上下文

Worker 在 Run 进入 `running` 后创建唯一的 `AgentRunContext`，并在该 Run 的执行
与终态处理结束后关闭。Context 负责：

- 持有当前 Run 唯一的进程内 `asyncio.Event`；
- 通过显式 `start()` / `close()` 启动并回收唯一的 Redis 取消监听任务；
- 通过 `wait_cancel_signal()` 提供统一等待入口；
- 让 `_cancellable_stream` 复用同一个取消信号，不再自行创建 Event 或 Redis
  监听任务。

Context 只表达 Worker 进程内的取消状态。PostgreSQL 仍是 Run 生命周期状态的
唯一事实来源，Redis key/Pub/Sub 的读写仍由 `arq_queue_servcie.py` 负责。

### RUN-CAN-006 Agent Stream 前停止

Worker 以是否已经进入 Agent Stream 消费循环区分取消事件写入：

- Agent Stream 消费循环前停止，只通过 `set_run_terminal` 提交 PostgreSQL
  终态，不调用 `_finalize_run`，也不向 `run:events:{run_id}` 写入 `end`；
- Agent Stream 消费循环内收到取消时，先释放所有非空 chunk bucket，再通过
  `set_run_terminal` 提交 `cancelled`，取得实际 `agent_status` 与 `changed`；仅在
  `changed=True` 且实际状态为 `cancelled` 时调用 `write_end_stream_event` 写入唯一
  Redis `end`；
- 用户取消终态写入后不调用 `clear_agent_run_cancel_signal`。

Stream 前未写入 Redis `end` 的取消终态由
[`RUN-ES-004`](../event-streaming/spec.md) 按 PostgreSQL 权威状态生成当前 SSE
响应，不得回写 Redis Stream。

### RUN-CAN-007 Agent Stream 取消异常收敛

Agent Stream 消费期间收到 Run 取消信号时，`_cancellable_stream` 必须取消并等待
当前 `anext()` 任务，显式捕获该任务产生的 `asyncio.CancelledError`，并直接使用
`asyncio.CancelledError` 结束流消费，不新增 Worker 自定义取消异常。

`process_agent_run` 捕获 `asyncio.CancelledError` 后直接调用一次
`StreamEventSmoother.release()`，再调用 `set_run_terminal(status="cancelled")` 并
接收实际 `agent_status` 与 `changed`。`process_agent_run` 不预读 Run 状态，也不遍历
`chunk_buckets`；PostgreSQL 当前状态及终态转换是否合法，由 `set_run_terminal`
内部的仓储写入负责。终态实际改变后，Worker 使用返回的实际状态写入 `end`，不得使用
请求写入的目标状态代替数据库返回状态。

`StreamEventSmoother.release()` 无参数调用负责释放该 Smoother 持有的全部待发送
bucket。调用方不得读取或遍历 `chunk_buckets`。

## 3. API Flow

```text
POST /api/agent/runs/{run_id}/cancel
  -> request_cancel_agent_run(run_id, current_uid)
     -> run_repository.request_cancel(run_id/children)
     -> publish run_id to AGENT_RUN_CANCEL_CHANNEL
  -> worker initial load does not collapse cancel_requested into cancelled
  -> worker reaches the pre-execution status checkpoint
     -> before Agent Stream: set_run_terminal(status="cancelled"), no Redis end
  -> worker.AgentRunContext watches Redis cancel signal
  -> worker._cancellable_stream waits on context.wait_cancel_signal()
  -> cancel current anext task and catch its asyncio.CancelledError
  -> process_agent_run catches asyncio.CancelledError
     -> stream_event_smoother.release()
     -> agent_status, changed = set_run_terminal(status="cancelled")
     -> changed and agent_status == cancelled: write_end_stream_event(...)
```

## 4. Data Model

- `request_cancel` 改为 `cancel_requested`
- 终态只允许由执行链路最终写入 `cancelled`

## 5. Acceptance Criteria

- 所有取消请求返回成功且不会破坏未取消子流程
- 取消后 run 最终 `status = cancelled`
- Agent Stream 前停止不创建 Redis `end`，SSE 根据 PostgreSQL 终态结束
- Agent Stream 内取消先释放已有 chunk bucket，再写 PostgreSQL `cancelled`，并只在
  终态实际改变时写入唯一 Redis `end`
- Agent Stream 前取消不会创建只有 `end` 的 Redis Stream
- 一个执行中的 Run 只创建一个 `asyncio.Event` 和一个 Redis 监听任务
- `_cancellable_stream` 退出时只回收自己创建的流消费任务和等待任务；Run Context
  在 Run 终态处理结束后回收 Redis 监听任务
- 不存在 Worker 自定义取消异常；流中断直接使用 `asyncio.CancelledError`
- `process_agent_run` 不预读 PostgreSQL 状态；`set_run_terminal` 以事务内当前 Run
  决定是否从 `cancel_requested` 收敛为 `cancelled`
- 取消处理只调用一次 `StreamEventSmoother.release()`，不暴露 bucket 遍历
- 取消终态写入后不调用 `clear_agent_run_cancel_signal`
- Redis `end.status` 来自 `set_run_terminal` 返回的实际 PostgreSQL 状态
