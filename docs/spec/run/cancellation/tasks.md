# Tasks: Run Cancellation

## Task Map

| Task ID | 关联需求 | 主要文件 | 说明 |
| --- | --- | --- | --- |
| CAN-001 | RUN-CAN-001 | `server/service/agent_run_service.py` | `request_cancel_agent_run` 标记当前/子 run |
| CAN-002 | RUN-CAN-001 | `server/service/arq_queue_servcie.py` | publish/cancel key 清理链路 |
| CAN-003 | RUN-CAN-002 | `server/worker.py` | `_cancellable_stream` 监听取消并中止执行 |
| CAN-004 | RUN-CAN-003 | `server/worker.py` | 取消时写 `status=cancelled` terminal event |

## Done 条件

- 取消可以中断正在执行的流
- 幂等性成立：多次取消不会抛异常
- 已完成 run 不被重复取消写坏状态
