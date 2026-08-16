# Tasks: Run Cancellation

## Task Map

| Task ID | 关联需求 | 主要文件 | 说明 |
| --- | --- | --- | --- |
| CAN-001 | RUN-CAN-001 | `server/service/agent_run_service.py` | `request_cancel_agent_run` 标记当前/子 run |
| CAN-002 | RUN-CAN-001 | `server/service/arq_queue_servcie.py` | publish/cancel key 清理链路 |
| CAN-003 | RUN-CAN-002、RUN-CAN-005 | `server/worker.py` | `_cancellable_stream` 复用 `wait_cancel_signal()` 并中止执行 |
| CAN-004 | RUN-CAN-003 | `server/worker.py` | 取消时写 `status=cancelled` terminal event |
| CAN-005 | RUN-CAN-005 | `server/worker.py` | `AgentRunContext` 通过 `start/wait_cancel_signal/close` 管理唯一取消监听 |
| CAN-006 | RUN-CAN-005 | `test/test_worker_stream_event_smoother.py` | 验证单监听、取消唤醒和任务回收 |

## Done 条件

- 取消可以中断正在执行的流
- 幂等性成立：多次取消不会抛异常
- 已完成 run 不被重复取消写坏状态
- 单个 Run 不重复创建取消 Event 或 Redis listener
- Run 正常、失败或取消退出时不遗留监听任务
