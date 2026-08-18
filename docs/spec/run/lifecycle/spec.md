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
    status="completed",
)
```

`set_run_terminal` 只接收 Run 终态字段 `status/error/error_type`，不得接收或持久化
`conversation_id/content`。输出消息持久化不属于 Run 终态写入职责。

### RUN-LC-003 终态回写并发保护
`set_agent_terminal` 必须拒绝非法回退；并发场景下仅允许一处成功写入终态。

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
