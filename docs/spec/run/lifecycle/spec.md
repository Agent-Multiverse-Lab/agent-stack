# Run Lifecycle Spec

## 1. Context

定义一次 Run 从创建到终态落库的行为约束，保证主流程可重试、可恢复、可审计。

## 2. Required States

- `pending -> queued -> running -> (completed | failed | cancelled)`
- `cancel_requested` 为中间中止态，允许转换到 `cancelled`
- 终态不可回退

## 3. Core Requirements

### RUN-LC-001 统一终态来源
`AgentRun` 终态必须由数据库仓储方法落库，流事件仅承载可观测数据。

### RUN-LC-002 执行完成入库
`worker` 执行结束后，按结果调用统一收口：

```python
run = await set_run_terminal(
    run_id,
    worker_id=owner_token,
    status="completed",
)
```

`set_run_terminal` 接收执行归属凭证 `worker_id` 和 Run 终态字段 `status/error/error_type`，不得接收或持久化
`conversation_id/content`。输出消息持久化不属于 Run 终态写入职责。

### RUN-LC-003 终态回写并发保护
`set_agent_terminal` 必须拒绝非法回退；并发场景下仅允许一处成功写入终态。

Worker 在 `startup(ctx)` 中生成进程身份，每次 Job 执行再追加 UUID，组成独立的
owner token。`AgentRun.worker_id` 保存该 token；Repository 不依赖 Worker 全局变量。

- `set_running` 在同一事务和行锁内检查状态与归属，只认领无 owner 的
  `pending/queued/cancel_requested` Run；认领取消中的 Run 时保留取消状态。
- Worker 在读取输入和执行准备前完成认领；已有执行者时退出，不执行 Agent。
- Worker 的终态和输出写入必须携带相同 token，在数据库行锁内核对当前归属。
- 无 token 的终态调用仅允许将尚未认领的 `pending/queued` Run 标记为入队失败，
  不能修改正在执行的 Run。用户取消通过 `request_cancel` 提交意图，不替换 owner。
- 允许重试的准备阶段异常，在交还 ARQ 前由当前 owner 释放归属；`running` 回到
  `pending`，`cancel_requested` 保持不变。下一次尝试生成新 token 并重新认领，旧 token
  不能写入终态、输出或再次释放归属。

### RUN-LC-004 `cancellation` 与终态一致
`cancel_requested` 不能直接变回 `running`；若终态已变更为 `completed`/`failed`/`cancelled`，后续 finalize 只读返回原状态。

### RUN-LC-005 Agent Stream 前终态分类

`server/worker.py:process_agent_run` 在进入 Agent Stream 消费循环前，不得把所有
停止统一解释为 `cancelled`：

- Run 不存在：无法写入终态，记录错误并返回；
- Run 已是 `completed/failed/cancelled`：保持当前终态并返回；
- 执行前检查仍为 `cancel_requested`：写入 `cancelled`，清理取消信号并返回；
- Message、User、Agent 或执行准备失败：写入 `failed`，同时保存对应
  `error/error_type` 并返回；
- `completed` 只表示 Agent 执行正常结束，不得用于取消或执行准备错误。

上述分支只 `await set_run_terminal(...)` 完成数据库副作用，不消费其返回值，也不
调用 `_finalize_run`。进入 Agent Stream 消费循环后的终态继续由 `_finalize_run`
收敛。Redis/SSE 终止遵循
[`RUN-ES-004`](../event-streaming/spec.md) 的 PostgreSQL 权威状态规则。

### RUN-LC-006 执行前显式重试

`WorkerSettings` 启用 ARQ 重试，每个 Job 最多执行 3 次（首次执行加两次重试）。
`RetryableWorkerError` 直接继承 `arq.worker.RetryJob`。Agent Stream 启动前仅
`RetryJob` 及其子类触发重新调度，由 ARQ 决定下一次执行时机；等待重试时
保留非终态，不写入 `failed` 或发布终态事件。重试耗尽后通过 `set_run_terminal`
保存失败原因，并向 ARQ 传播普通异常以结束 Job。
每次重试重新读取 SQL Run，已有终态与执行前取消检查继续生效。
普通 `Exception`（包括连接和超时异常）保存失败终态，不自动转换成重试信号。
Agent Stream 已启动后的错误、业务错误 chunk、缺失输入和用户，以及业务取消
继续使用现有终态流程，避免整个 Agent 重放导致重复工具副作用。

## 4. Failure Contract

- `running` 异常 -> `failed` + `error/error_type`
- 解析/执行异常不能导致状态丢失，必须可通过 DB 查询到失败原因
- `set_run_terminal` 抛出异常时，调用方应在高层终止并抛出（不静默吞掉非 `failed`）

## 5. Acceptance Criteria

- 所有终态路径会落库：`completed / failed / cancelled`
- 同一 run 的终态确定后不得发生反向变更
- 任何对终态的写入调用需通过仓储 `set_agent_terminal`
- Agent Stream 前的停止原因会被分类为不存在、既有终态、取消或失败，不使用统一
  的 `cancelled` 代替真实结果
