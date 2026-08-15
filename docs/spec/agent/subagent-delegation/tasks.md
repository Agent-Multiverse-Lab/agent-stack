# Tasks: Subagent Delegation

## Task Map

| Task ID | 关联需求 | 主要文件 | 说明 |
| --- | --- | --- | --- |
| SUB-001 | AG-SUB-001 | `src/agents/middlewares/subagent_middlware.py` | 统一子代理调用路径 |
| SUB-002 | AG-SUB-002 | `src/database/repositories/agent_run_repository.py` | 父子 run 查询与限制 |
| SUB-003 | AG-SUB-003 | `server/service/agent_run_service.py` | run_type/parent_run_id 数据完整 |
