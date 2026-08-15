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
Worker 感知取消后写入 `cancelled`（若仍处于可中断态），并清理 `run:cancel:{run_id}`。

### RUN-CAN-004 统一终态
一旦 DB 状态变为 `completed/failed`，后续取消不能覆盖终态。

## 3. API Flow

```text
POST /api/agent/runs/{run_id}/cancel
  -> request_cancel_agent_run(run_id, current_uid)
     -> run_repository.request_cancel(run_id/children)
     -> publish run_id to AGENT_RUN_CANCEL_CHANNEL
  -> worker._cancellable_stream detects signal
  -> AgentRunCancelRequested -> _finalize_run(status="cancelled")
```

## 4. Data Model

- `request_cancel` 改为 `cancel_requested`
- 终态只允许由执行链路最终写入 `cancelled`

## 5. Acceptance Criteria

- 所有取消请求返回成功且不会破坏未取消子流程
- 取消后 run 最终 `status = cancelled`
- `end` 事件类型与终态一致
