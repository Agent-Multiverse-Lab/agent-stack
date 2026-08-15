# Tasks: Context Management

## Task Map

| Task ID | 关联需求 | 主要文件 | 说明 |
| --- | --- | --- | --- |
| AGM-001 | AG-CONT-001/002 | `server/worker.py` | 明确上下文构建输入，不从全局读取 |
| AGM-002 | AG-CONT-003 | `server/service/thread_service.py` | 明确 stream 入参含 runtime context |
| AGM-003 | AG-CONT-003 | `src/agents/leaderagent/agent.py` | context 入参消费点归档 |
