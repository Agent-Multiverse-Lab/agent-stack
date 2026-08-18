# Tasks: Run Event Streaming

## Task Map

| Task ID | 关联需求 | 主要文件 | 说明 |
| --- | --- | --- | --- |
| ES-001 | RUN-ES-001 | `server/service/agent_run_service.py` | 删除旧 event builder 和无调用的发布包装 |
| ES-002 | RUN-ES-002/004 | `server/service/agent_run_service.py` | 按 envelope 读取进度，并根据 PostgreSQL 终态生成公共 end |
| ES-003 | RUN-ES-003 | `server/utils/agent_run_utils.py` | 将完整 envelope 格式化为现有 SSE frame |
| ES-004 | RUN-ES-005 | `server/service/arq_queue_servcie.py`, `server/worker.py` | 三个 writer 统一使用 `payload` 参数，并接入普通写入与 end 写入调用点 |
| ES-005 | RUN-ES-001/003/005 | `test/test_agent_run_service.py`, `test/test_worker_stream_event_smoother.py` | 验证唯一 builder、payload 读取、SSE 契约与 Worker 参数转发 |
| ES-006 | RUN-ES-001/003/005 | `AGENTS.md` | 同步 envelope、Worker writer 与 SSE formatter 职责边界 |
| ES-007 | RUN-ES-004 | `server/service/agent_run_service.py` | 每轮先重查 PostgreSQL，排空普通事件后生成唯一公共 end |
| ES-008 | RUN-ES-004/005 | `test/test_agent_run_service.py` | 验证 Redis end 只唤醒重查及 Agent Stream 前的数据库终止路径 |

## Done 条件

- `agent_run_service.py` 不再构造或发布 Agent Run 消息。
- Redis envelope 只由 `arq_queue_servcie.py` 构造。
- SSE formatter 无数据库和 Redis 依赖。
- Redis `event_type=end` 只唤醒 PostgreSQL 状态重查，不直接结束 SSE。
- PostgreSQL 已终态且普通事件排空后，SSE 生成唯一 `data.type=end` 并结束。
- PostgreSQL 驱动生成的公共终态不会重复写入 Redis。
- 队列 writer 与 Worker 两个 writer 对事件体统一使用 `payload` 参数。
- Worker 的两个 writer 只做 payload 转发与 `end` 类型固定，不增加其他副作用。
