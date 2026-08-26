# Tasks: Run Interrupt and Resume

## Ordered Tasks

| Task ID | 关联需求 | 主要文件 | 完成条件 |
| --- | --- | --- | --- |
| RHI-001 | RUN-HIL-005/007/008 | `test/test_agent_run_interrupt_resume.py` | 固定 LangGraph 1.2.9 `StateSnapshot.interrupts` 结构；`Command(resume=answer)` 生成关联 ToolMessage 并继续 |
| RHI-002 | RUN-HIL-001/002/006 | `src/database/models.py`、`src/database/repositories/agent_run_repository.py` | `set_interrupted` 原子保存 metadata/状态；父 Run 至多一个 Resume 子 Run |
| RHI-003 | RUN-HIL-003/004 | `server/entities/agent.py`、`server/router/agent_router.py`、`server/service/agent_run_service.py` | `AgentRunResumeRequest` 沿用 `thread_metadata`；旧 Run ID 定位父 Run，新 Run ID 保存 `run_metadata.resume` 并独立入队 |
| RHI-004 | RUN-HIL-005/007 | `src/agents/base_agent.py`、`server/service/thread_service.py` | 新增 Resume 专用 `stream_message_by_resume`；`resume_agent_response` 构造 Command 后调用它；`check_agent_interrupt_handler` 获取 state；`build_agent_interrupt_message` 构造 question/options；普通与 Resume 流 yield 相同 chunk 合同 |
| RHI-005 | RUN-HIL-006/007/009 | `server/worker.py` | `process_agent_run` 在读取普通 Message 前选择普通/Resume 入口；按 chunk status 调用统一 `_finalize_run`；只有实际停止状态且 `changed=True` 时发布停止事件；不使用 interrupt 专用 finalizer 或循环 `break` |
| RHI-006 | RUN-HIL-008 | `server/service/thread_service.py`、Message/ToolCall Repository | checkpoint 重读不重复插入 Message/ToolCall；`save_message_from_langgraph_state` 保持 `None` 返回值 |
| RHI-007 | RUN-HIL-005/007 | `src/agents/leaderagent/tools.py`、`src/agents/leaderagent/agent.py` | 仅 LeaderAgent 注册 `ask_user(question, options)`，interrupt payload 包含 question/options，不新增工具注册器 |
| RHI-008 | RUN-HIL-010/011 | `server/service/thread_service.py`、`web/src/types/chat.ts`、`web/src/api/agent.ts`、`web/src/composables/useAgentRun.ts` | 前端提交父 Run ID 和 `thread_metadata.resume`，切换到新 Run Stream，并支持刷新恢复 |
| RHI-009 | RUN-HIL-010/011 | `web/src/views/ChatView.vue`、`web/src/components/chat/hil/ChatAskUserComponent.vue` | 提问组件渲染真实 question/options 并提交单选 answer；待回答时禁止普通提交 |
| RHI-010 | RUN-HIL-001~011 | 后端与前端定向测试 | 正向、负向、重复打断、刷新恢复、取消独立性、终止状态 `changed=True/False`、stream 自然耗尽和构建检查通过 |

## Execution Gates

1. RHI-001 通过前，不实现 interrupt parser。
2. RHI-003~005 通过前，不把 `ask_user` 注册到 LeaderAgent。
3. RHI-006 通过前，不宣称 Resume 消息持久化可用。
4. 后端 Resume 和事件合同通过后，再连接前端真实交互。

## Done Conditions

- 父 Run 保持 `interrupted`，新 Resume Run 使用明确的 `parent_run_id`；
- 旧 Run ID 只用于定位和校验，新 Run ID 用于入队、Worker 和 SSE；
- 请求的 `thread_metadata` 复制为 `run_metadata`，其中 `resume` 承载恢复数据，`msg_metadata` 不参与；
- Resume 不创建 HumanMessage，不重放父输入，不重复保存历史消息；
- `stream_messages_with_event` 只处理普通 messages，`stream_message_by_resume` 只处理
  `Command(resume=answer)`；`resume_agent_response` 不委托 `stream_agent_response`；
- `check_agent_interrupt_handler` 独立获取 state，
  `build_agent_interrupt_message` 按 ask_user 合同构造 question/options，不读取 values event，
  普通入口内部使用 `make_agent_stream_event`，Resume 入口内部使用
  `make_agent_resume_event`，并 yield 字段合同一致的 chunk，
  `process_agent_run` 按 chunk status 调用统一 `_finalize_run`，等待 stream 自然耗尽；
- 不保留 `_finalize_interrupted_run`；Repository 的普通终态与 interrupted 写入仍分离；
- `_finalize_run` 返回实际 `agent_status/changed`，只有停止状态且 `changed=True` 时由当前
  Worker 发布停止事件，`changed=False` 不重复发布；
- 只有显式 `finished` chunk 写 completed，无停止 status 的流耗尽写 failed；
- `ask_user` 回答生成一个关联 ToolMessage，随后模型继续输出；
- 越权、错误 Thread、重复恢复和缺失 checkpoint 均有确定结果；
- 刷新可恢复 active Run 或 pending interaction，取消与打断保持独立。
