# Tasks: Run Lifecycle

## Task Map

| Task ID | 关联需求 | 主要文件 | 说明 |
| --- | --- | --- | --- |
| RLC-001 | RUN-LC-001/002 | `server/worker.py` | 统一 `_finalize_run` 的终态写入与事件落盘 |
| RLC-002 | RUN-LC-003 | `src/database/repositories/agent_run_repository.py` | 终态守卫与并发安全 |
| RLC-003 | RUN-LC-002 | `server/service/agent_run_service.py` | 终态 SSE 兜底读取与补齐 end |
| RLC-004 | RUN-LC-004 | `test/test_worker_stream_event_smoother.py` | 验证完成/失败/取消不会互相覆盖 |

## Done 条件

- 终态写入调用只来自 worker 统一收口
- 事件与 DB 终态一致
- 重复调用 `_finalize_run` 不改变已完成状态
