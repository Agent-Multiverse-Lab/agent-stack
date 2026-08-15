# Tasks: State Ownership

## Task Map

| Task ID | 需求 | 文件 | 说明 |
| --- | --- | --- | --- |
| POS-001 | PS-OWN-001 | `src/database/repositories/agent_run_repository.py` | 明确终态写入入口 |
| POS-002 | PS-OWN-002/003 | `server/service/arq_queue_servcie.py` | Redis key TTL 与清理 |
| POS-003 | PS-OWN-001 | `server/service/agent_run_service.py` | SSE 终态兜底与 DB 真相一致 |
