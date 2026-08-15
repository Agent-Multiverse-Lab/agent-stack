# Tasks: Run Event Streaming

## Task Map

| Task ID | 关联需求 | 主要文件 | 说明 |
| --- | --- | --- | --- |
| ES-001 | RUN-ES-001 | `server/worker.py` | 统一事件写入点 |
| ES-002 | RUN-ES-002 | `server/service/agent_run_service.py` | SSE 事件读取与 cursor 管理 |
| ES-003 | RUN-ES-003 | `server/service/arq_queue_servcie.py` | Stream key 与 TTL/读取封装 |
| ES-004 | RUN-ES-002/003 | `server/router/agent_router.py` | SSE endpoint 的终止策略 |

## Done 条件

- SSE 在收到 end 时结束
- 重连后能按 event-id 持续读取
- DB 终态兜底事件不会重复污染已存在终态
