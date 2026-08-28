# Implementation Plan: Worker Stop-Case Preemption Publish

计划版本：`v0.2.0`

归档状态：已完成。

## 1. 目标

本次只调整 `server/worker.py:process_agent_run` 对父 Run 的三个停止 chunk：
`status="error"`、`status="finished"` 和 `status="interrupted"`。

每个 case 必须按同一顺序执行：

1. 先调用现有 `_finalize_run`；
2. 从返回值取得 PostgreSQL 中的实际 `(agent_status, changed)`；
3. `changed=True` 时，在当前 case 内部调用一次 `write_end_stream_event`，发布当前 chunk；
4. 最后在当前 case 内执行
   `terminal_flag = agent_status in AGENT_RUN_TERMINAL_STATUSES`。

`_finalize_run` 与 case 的事件发布职责同时保留。前者继续执行当前内部发布逻辑；后者根据
同一次 `_finalize_run` 返回的 `changed` 做二次发布。两次发布是本次明确要求的行为，不做
去重，也不把 `_finalize_run` 改成只写数据库的函数。

## 2. 范围

### 2.1 本次修改

- `docs/spec/run/interrupt-resume/spec.md`
  - 把 RUN-HIL-006 更新为 v0.2.0 的双层发布合同；
  - 明确 `changed` 决定当前 case 是否二次发布；
  - 明确三个停止 case 分别在内部根据实际 `agent_status` 设置 `terminal_flag`，不依据
    `changed`。
- `server/worker.py:process_agent_run`
  - 用 `terminal_flag: bool` 替代 `terminal_result`；
  - 调整 `error/finished/interrupted` 三个父 Run case；
  - stream 自然耗尽后读取 `terminal_flag`，为真时裸返回。
- `test/test_worker_stream_event_smoother.py`
  - 固定三个 case 的调用顺序、changed 分支、二次 end payload 和
    `terminal_flag` 行为。

### 2.2 本次不修改

- 不删除、不收窄 `_finalize_run` 的事件发布逻辑；
- 不修改 `_finalize_run`、`set_run_terminal`、`set_agent_terminal` 的参数或返回值；
- 不修改 `cancelled`、执行前失败、执行前取消、无停止 chunk、异常兜底的现有路径；
- 不修改 Thread Service 的 chunk builder、Repository、Redis writer、SSE 读取端或前端；
- 不增加 helper、事件类型、Redis key、重试层或兼容分支；
- 不在停止 case 内使用 `break`、`continue` 或立即 `return` 截断 Agent stream。

## 3. 控制流设计

### 3.1 并发语义

`_finalize_run` 返回的 `changed` 来自 PostgreSQL 状态转换结果：

- `changed=True`：本次调用修改了数据库状态。`_finalize_run` 先完成现有发布，随后当前
  case 再发布携带当前 chunk 的 `end`；
- `changed=False`：其他路径已经完成状态转换。当前 case 不进行二次发布；
- 每个 case 都在内部使用实际 `agent_status` 计算 `terminal_flag`，与 `changed` 无关。因此
  `changed=False` 但状态已经停止时，不会在 stream 耗尽后进入取消或协议错误兜底。

固定顺序如下：

```text
decoded stop chunk
  -> _finalize_run(...)
       -> set_run_terminal(...)
       -> 保留 _finalize_run 当前的 changed-only 事件发布
       -> return (agent_status, changed)
  -> if changed: case write_end_stream_event(...current chunk...)
  -> terminal_flag = agent_status in AGENT_RUN_TERMINAL_STATUSES
  -> 继续自然消费 stream
```

### 3.2 二次 end payload

case 的二次发布必须同时保留外部 Run 状态和本次 Thread Service 原始停止消息：

```python
case_end_payload = {
    "status": agent_status,
    "chunk": strem_agent_chunk,
}
```

顶层 `status` 使用 PostgreSQL 返回的实际状态；`chunk.status` 保留 Thread Service 的内部
停止信号。三种映射为：

| 当前 chunk | `_finalize_run` 目标状态 | 二次 end 顶层状态 | `chunk.status` |
| --- | --- | --- | --- |
| `error` | `failed` | 实际 `agent_status`，正常为 `failed` | `error` |
| `finished` | `completed` | 实际 `agent_status`，正常为 `completed` | `finished` |
| `interrupted` | `interrupted` | 实际 `agent_status`，正常为 `interrupted` | `interrupted` |

不直接把内部 `error/finished` 写成顶层公开状态，也不丢弃当前 chunk 的
`error/error_type`、`request_id` 或 `interrupt` 等字段。

### 3.3 三个 case

目标：`server/worker.py:process_agent_run`

```python
terminal_flag = False

# 父 Run 的三个停止 case 分别在内部设置 terminal_flag。
if status == "interrupted":
    agent_status, changed = await _finalize_run(
        run_id,
        status="interrupted",
        thread_id=str(thread_id),
        payload=interrupt_payload,
    )
    if changed:
        await write_end_stream_event(
            run_id,
            {"status": agent_status, "chunk": strem_agent_chunk},
            current_thread_id,
        )
    terminal_flag = agent_status in AGENT_RUN_TERMINAL_STATUSES

elif status == "error":
    agent_status, changed = await _finalize_run(
        run_id,
        status="failed",
        thread_id=str(thread_id),
        error=strem_agent_chunk.get("error"),
        error_type=strem_agent_chunk.get("error_type"),
    )
    if changed:
        await write_end_stream_event(
            run_id,
            {"status": agent_status, "chunk": strem_agent_chunk},
            current_thread_id,
        )
    terminal_flag = agent_status in AGENT_RUN_TERMINAL_STATUSES

elif status == "finished":
    agent_status, changed = await _finalize_run(
        run_id,
        status="completed",
        thread_id=str(thread_id),
        payload=strem_agent_chunk,
    )
    if changed:
        await write_end_stream_event(
            run_id,
            {"status": agent_status, "chunk": strem_agent_chunk},
            current_thread_id,
        )
    terminal_flag = agent_status in AGENT_RUN_TERMINAL_STATUSES
```

三个 case 均不提前控制循环。退出数据库上下文并释放 smoother 后只读取布尔值：

```python
await stream_event_smoother.release()
if terminal_flag:
    return
```

`process_agent_run` 不返回 `(agent_status, changed)` 业务结果；状态和事件分别通过 PostgreSQL
与 Redis Stream 流转。

## 4. `_finalize_run` 保留合同

目标：`server/worker.py:_finalize_run`

本次不修改该函数。实现后仍保持：

- 统一调用 `set_run_terminal`；
- interrupted 继续把 payload 序列化到 `error/error_type`；
- `changed=True` 时继续发布它当前负责的普通 `end`，或 interrupted 的
  `interaction_required + end`；
- cancelled 继续清理取消信号；
- 返回 PostgreSQL 实际 `(agent_status, changed)`。

因此一次 `changed=True` 的父 Run 停止 chunk 会先产生 `_finalize_run` 当前已有的事件，再产生
case 的第二个 `end`。测试必须按该顺序断言，不能把第二个 `end` 当作重复事件删除。

## 5. 边界与失败处理

- 子 Agent chunk 继续只转发，不参与父 Run finalize、二次发布或 `terminal_flag`；
- `changed=False` 时不得调用 case 内的 `write_end_stream_event`，但仍应设置
  `terminal_flag=True`（前提是实际状态属于停止常量）；
- case 二次发布失败沿用当前异常传播和 PostgreSQL 权威状态约束，本次不增加静默吞错、重试或
  补偿队列；
- 一个停止 chunk 之后仍出现过程 chunk 时继续按 status 处理，直到 Thread Service stream
  自然耗尽；
- 没有任何父 Run 停止 chunk 时，`terminal_flag` 保持 `False`，继续走现有取消检查或
  “Agent stream ended without terminal status” 失败兜底；
- 实际 `agent_status` 为 `None` 或不属于 `AGENT_RUN_TERMINAL_STATUSES` 时，
  `terminal_flag=False`，不新增额外异常分支。

## 6. 测试设计

目标：`test/test_worker_stream_event_smoother.py:AgentRunProcessTest`

定向测试覆盖：

1. `error + changed=True`：顺序为 running status、finalize 内部事件、case 二次 end；二次
   payload 顶层为 `failed`，`chunk.status="error"`；
2. `finished + changed=True`：二次 payload 顶层为 `completed`，并保留完整 finished chunk；
3. `interrupted + changed=True`：先保留 finalizer 的
   `interaction_required + end`，再出现 case 二次 end；
4. 三种 case 的 `changed=False`：不出现 case 二次 end，stream 耗尽后也不进入兜底；
5. `agent_status` 已是另一停止状态且 `changed=False`：`terminal_flag` 仍为真；
6. 停止 chunk 后跟随过程 chunk：过程 chunk 仍被转发，证明 case 未提前结束循环；
7. 无停止 chunk：保持现有取消和协议错误路径，不因本次改动改变其事件数量或返回行为。

实现获批后的验证命令：

```powershell
uv run --no-sync python -m unittest -v test.test_worker_stream_event_smoother
uv run ruff check server/worker.py test/test_worker_stream_event_smoother.py
python -m py_compile server/worker.py test/test_worker_stream_event_smoother.py
git diff --check -- docs/spec/run/interrupt-resume/spec.md server/worker.py test/test_worker_stream_event_smoother.py
```

以上仅证明定向 Worker 行为和静态质量，不宣称完成真实 Redis/ARQ 并发运行验证。

## 7. 完成结果

本计划已按第 2.1 节范围实施，只修改现行 spec、Worker 三个停止 case 和定向测试；
`_finalize_run`、取消路径及其他系统边界保持不变。定向 unittest、Ruff、语法检查和 diff
检查均通过。
