# Tasks: Agent Run Message Persistence

## Task Map

| Task ID | 关联需求 | 主要文件 | 说明 |
| --- | --- | --- | --- |
| MP-001 | RUN-MP-001/007 | `src/database/models.py`, `migrate/versions/0007_agent_run_message_persistence.py` | 增加 Run 输出指针，删除 ToolCall 排序字段并增加可空 `status` |
| MP-002 | RUN-MP-002/005/006 | `src/database/repositories/conversation_repository.py` | 创建 Assistant Message/ToolCall，按 `tool_call_id` 更新 ToolCall，并按 Run 输出指针查询 Message |
| MP-003 | RUN-MP-001/005 | `src/database/repositories/agent_run_repository.py` | 将新建 Assistant Message ID 写入 `AgentRun.output_message_id` |
| MP-004 | RUN-MP-003/004/005/006 | `server/service/thread_service.py` | 从 checkpoint 读取 Message，按 `type` 调用两个 save 函数 |
| MP-005 | RUN-MP-008 | `server/service/thread_service.py:stream_agent_response` | 在 `finished` 前保存并提交 Message/ToolCall |
| MP-006 | RUN-MP-001/002/003/004/005/006/007/008 | `test/test_thread_message_persistence.py` | 用固定 state 验证完整持久化、输出指针和删除级联 |

## Ordered work

1. 完成 AgentRun/ToolCall schema 和 Alembic revision。
2. 在 Conversation Repository 内完成 ToolCall 创建/更新和 Run 结果查询。
3. 在 AgentRun Repository 内完成输出 Message 指针更新。
4. 完成 Thread Service 的三个 save 函数和正常完成调用点。
5. 增加一个 Message 遍历闭环测试并运行定向检查。

## Done Conditions

- `ToolCall` 不再包含或接收排序值；
- AI Message 的 `id/name/args` 通过 `ConversationRepository.create_tool_call`
  写入一个 ToolCall；
- Tool Message 的 `tool_call_id/text/status` 通过
  `ConversationRepository.update_tool_call` 更新同一 ToolCall；
- 两条 AI Message 都通过 `Message.agent_run_id` 关联当前 Run，
  `AgentRun.output_message_id` 最终指向最后一条；
- Run 结果查询通过 `output_message_id` 返回最终 Message；
- Conversation 物理删除时，Message 和 ToolCall 由外键按层级级联删除；
- 数据库事务完成后才产生 `finished`；
- 没有 fallback、幂等扩展或其他事件链路修改；
- 定向 unittest、compileall、migration 和 diff check 通过并如实报告。
