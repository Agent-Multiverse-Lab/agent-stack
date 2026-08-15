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
    conversation_id=int(agent_run_event.conversation_id),
    content=result_text,
)
```

### RUN-LC-003 终态回写并发保护
`set_agent_terminal` 必须拒绝非法回退；并发场景下仅允许一处成功写入终态。

### RUN-LC-004 `cancellation` 与终态一致
`cancel_requested` 不能直接变回 `running`；若终态已变更为 `completed`/`failed`/`cancelled`，后续 finalize 只读返回原状态。

## 4. Failure Contract

- `running` 异常 -> `failed` + `error/error_type`
- 解析/执行异常不能导致状态丢失，必须可通过 DB 查询到失败原因
- `set_run_terminal` 抛出异常时，调用方应在高层终止并抛出（不静默吞掉非 `failed`）

## 5. Acceptance Criteria

- 所有终态路径会落库：`completed / failed / cancelled`
- 同一 run 的终态确定后不得发生反向变更
- 任何对终态的写入调用需通过仓储 `set_agent_terminal`
