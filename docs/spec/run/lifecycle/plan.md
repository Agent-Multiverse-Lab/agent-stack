# Implementation Plan: Run Lifecycle

计划版本：`v0.2.0`

本文件只承载当前版本；已实施计划位于 `history/<version>/plan.md`。

## 1. Implementation Steps

1. 在 `server/worker.py:process_agent_run` 中保留 Run 不存在和既有终态的裸
   `return`；这两类分支不调用 `set_run_terminal`。
2. 删除初次加载到 `cancel_requested` 就调用 `_finalize_run` 的分支，继续执行到
   `set_run_running` 后的统一执行前状态检查点。
3. 执行前检查为 `cancel_requested` 时，直接
   `await set_run_terminal(status="cancelled")`，清理取消 key 后裸 `return`。
4. Message、User、Agent 或其他执行准备失败时，直接
   `await set_run_terminal(status="failed", error=..., error_type=...)` 后裸
   `return`，不写成 `cancelled`。
5. 进入 `_cancellable_stream` 的 Agent Stream 消费循环后，正常完成、执行失败和
   执行中取消继续调用 `_finalize_run`。
6. PostgreSQL 终态与公共 SSE `end` 遵循
   [`RUN-ES-004`](../event-streaming/spec.md)：Redis `end` 只唤醒状态重查，SSE
   根据数据库中的实际 `completed/failed/cancelled` 生成终态。
7. 更新定向测试与 `AGENTS.md`，覆盖执行前各类原因不会写错终态。
8. 简化 `server/worker.py:set_run_terminal` 与 `_finalize_run`：删除未使用的
   `conversation_id/content` 参数、completed 参数校验、空 `Message UPDATE` 和调用方
   转发。终态写入只保留 `status/error/error_type`；本计划不新增输出消息持久化。

## 2. Terminal Classification

| Agent Stream 前条件 | 数据库动作 | 后续动作 |
| --- | --- | --- |
| Run 不存在 | 无法写入 | 记录错误，裸 `return` |
| 已是 `completed/failed/cancelled` | 不修改 | 裸 `return` |
| `cancel_requested` | `set_run_terminal(status="cancelled")` | 清理 cancel key，裸 `return` |
| Message/User/Agent/准备错误 | `set_run_terminal(status="failed", error, error_type)` | 裸 `return` |

`completed` 不属于执行前停止结果，只能由 Agent Stream 正常完成路径产生。

## 3. Core Examples

### 3.1 Run 不存在或已有终态

目标：`server/worker.py:process_agent_run`

```python
if agent_run_event is None:
    logger.error("Agent Run 不存在：%s", run_id)
    return

if initial_status in {"completed", "failed", "cancelled"}:
    return
```

### 3.2 执行前取消

目标：`server/worker.py:process_agent_run`

```python
await set_run_terminal(run_id, status="cancelled")
await clear_agent_run_cancel_signal(run_id)
return
```

### 3.3 执行准备失败

目标：`server/worker.py:process_agent_run`

```python
await set_run_terminal(
    run_id,
    status="failed",
    error="Agent 不存在",
    error_type="LookupError",
)
return
```

三个示例使用现有控制流和 `set_run_terminal`，不新增统一结果对象、状态映射器或
辅助函数。

### 3.4 纯 Run 终态接口

目标：`server/worker.py:set_run_terminal`

```python
async def set_run_terminal(
    run_id: str,
    *,
    status: str,
    error: str | None = None,
    error_type: str | None = None,
) -> tuple[str | None, bool]:
    ...
```

该接口不创建或更新 `Message`，也不接收 Conversation 或输出内容。

## 4. Failure Handling

- 失败原因必须写入 `error/error_type`，不得伪装成取消。
- 取消路径只在数据库状态仍为 `cancel_requested` 时转换为 `cancelled`。
- `set_run_terminal` 抛出异常时由 Worker 任务失败处理，不继续执行 Agent Stream。
- Agent Stream 前的数据库终态不产生 Redis `end`，SSE 根据数据库状态结束。

## 5. Scope Limits

- 不新增 Run 状态、数据字段、结果类型、映射器或异常层级。
- 不修改 Run 创建、cancel API、Repository 终态防竞态或 Agent Stream 内容。
- 不把所有执行前停止统一成同一个终态。
- 不在 Run 终态 setter 中补做输出消息持久化。

## 6. Validation

- 运行 `test/test_worker_stream_event_smoother.py` 的定向 `unittest`。
- 对 `server/worker.py` 与对应测试运行 `compileall`。
- 运行 `git diff --check`。
