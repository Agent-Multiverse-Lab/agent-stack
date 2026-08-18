# Tasks: Run Cancellation

## Task Map

| Task ID | 关联需求 | 主要文件 | 说明 |
| --- | --- | --- | --- |
| CAN-001 | RUN-CAN-001 | `server/service/agent_run_service.py` | `request_cancel_agent_run` 标记当前/子 run |
| CAN-002 | RUN-CAN-001 | `server/service/arq_queue_servcie.py` | publish/cancel key 清理链路 |
| CAN-003 | RUN-CAN-002、RUN-CAN-005、RUN-CAN-007 | `server/worker.py` | `_cancellable_stream` 复用 `wait_cancel_signal()`，直接以 `CancelledError` 中止执行，不保留自定义取消异常 |
| CAN-004 | RUN-CAN-003、RUN-CAN-006、RUN-CAN-007 | `server/worker.py` | Worker 捕获取消后依次 release、写 PostgreSQL 终态，并按实际返回状态写唯一 Redis `end` |
| CAN-005 | RUN-CAN-005 | `server/worker.py` | `AgentRunContext` 通过 `start/wait_cancel_signal/close` 管理唯一取消监听 |
| CAN-006 | RUN-CAN-005、RUN-CAN-007 | `test/test_worker_stream_event_smoother.py` | 验证单监听、取消唤醒、单次 `release()`、仓储终态写入和任务回收 |
| CAN-007 | RUN-CAN-006、RUN-ES-004 | `server/worker.py` | 用户取消统一只写数据库终态，已有 bucket 先释放，SSE 按 PostgreSQL 状态结束 |
| CAN-008 | RUN-CAN-006、RUN-CAN-007 | `test/test_worker_stream_event_smoother.py` | 验证 Stream 前取消无 `end`，Stream 内取消按实际数据库状态写唯一 `end`，且不清理 cancel key |

## Done 条件

- 取消可以中断正在执行的流
- 幂等性成立：多次取消不会抛异常
- 已完成 run 不被重复取消写坏状态
- 单个 Run 不重复创建取消 Event 或 Redis listener
- Run 正常、失败或取消退出时不遗留监听任务
- Agent Stream 前停止不写 Redis `end`，SSE 根据 PostgreSQL 终态结束
- Agent Stream 内取消先释放已有 bucket，再写 PostgreSQL `cancelled`，最后按实际状态
  写唯一 Redis `end`
- 无 chunk 的取消不会创建孤立 Redis Stream
- 流消费直接使用 `CancelledError`；只有 PostgreSQL 状态为 `cancel_requested` 时才
  收敛为 Run 的 `cancelled`
