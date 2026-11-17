# Agent Run 分发策略与前端等待区计划

## 1. 当前任务

在现有 `AgentRunRequest` 与 `AgentRun` 并发门禁基础上，将普通等待区排队（`queue`）收敛为前端未发送请求包（支持 0 延迟删除、一键强制插入与 Run 正常完成后自动发送），并为 `POST /api/agent/runs` 引入 `dispatch_policy`（`reject` / `steer`），实现 Turn 边界 `before_model` `jump_to="end"` 优雅停机、非正常消息 `save` 收敛，以及 Run 终态后的自动晋升调度。

数据契约与流程图见 [spec.md](../../spec.md)。

## 2. 任务目标

1. 为 `AgentRunCreateRequest` 与 `AgentRunRequest` 增加 `dispatch_policy`（`reject` / `steer`）、转向等待状态 `status` 与顺序号 `queue_seq`，保持 `AgentRun` 单活约束与 `enqueue_agent_run` 契约不变。
2. 普通排队等待（`queue`）保存在前端内存中，未实际执行前不写入数据库，删除操作直接移除前端内存项（0 延迟、不留取消墓碑）；仅 `steer`（强制插入）向后端发起请求。
3. 通过 LangGraph `before_model` middleware 的 `jump_to="end"` 实现 Turn 边界优雅停机，保证已执行 `tool_calls` 与 `ToolMessage` 完整闭合，保留 `_cancellable_stream` 硬取消作为兜底。
4. 统一非正常结束与正常结束的 `save` 路径：先 `save_message_from_langgraph_state` 同步已提交 checkpoint，再 reconcile 半截流式输出，补齐 `resume_agent_response` 的 `full_msg`。

## 3. 如何修改

1. **持久化与接口层**：移除 `AgentRunRequest` 冗余的 `conversation_id` 列（以 `thread_id` 索引逻辑关联会话，不建外键），扩展 `dispatch_policy`、`status`、`queue_seq` 与 Alembic 迁移；更新 `AgentRunRequestRepository` 与 `AgentRunRequestInput` 支持 `steer` 入队与按 `queue_seq` 出队晋升；调整 `create_agent_run_service` 在会话行锁下按 `reject / steer` 路由。
2. **运行时与调度层**：在 `LeaderAgent` 装配 `SteerStopMiddleware`（`before_model(can_jump_to=["end"])`），直接查询当前 `thread_id` 下是否存在 `status == "queued"` 且 `dispatch_policy == "steer"` 的 `AgentRunRequest`，不向 Redis 写入额外转向信号；在 `server/worker.py` 的 `_finalize_run` 终态提交后及租约回收器收敛后调用 `dispatch_next_queued_request(thread_id)` 晋升下一条转向请求并调用 `enqueue_agent_run`。
3. **消息保存层**：重构 `server/service/thread_service.py` 的终止保存顺序，令 `CancelledError` / 异常 / `steer` 停机先同步 checkpoint，再统一 reconcile 未入 checkpoint 的 `accumulated_msg`，避免重复插消息与审计行残留。
4. **前端交互层**：在 `ChatPage.tsx` 维护未发送等待区队列 `queuedSubmissions`，支持 0 延迟删除、一键 `Steer` 强制插入，以及当前 Run `completed` 后自动发出下一条请求；`api/agent-run.ts` 与 `useAgentRun` 支持 `202 queued` 转向响应及活跃 Run 终态后自动接续新 `active_run` SSE。

## 4. 实施步骤（计划）

1. 完成数据库迁移与 `AgentRunRequestRepository` 转向队列方法，调整 `Message` 在 `queued` 态的会话历史过滤。
2. 更新 `create_agent_run_service` 与 `agent_router.py`，落地 `reject` / `steer` 路由。
3. 落地 `SteerStopMiddleware`（基于 `AgentRunRequest` 状态检查并在 `before_model` 跳 `END`）及 Worker 终态后的 `dispatch_next_queued_request` 晋升逻辑。
4. 重构 `thread_service.py` 的非正常消息 `save` 收敛并修复 `resume_agent_response` 缺失 `full_msg`。
5. 在前端实现未发送等待区队列（0 延迟删除、强制插入、完成后自动发送）及 `steer` 切流。
6. 补充单元测试与集成测试，执行迁移与检查。

## 5. 验收标准

- 遵循 [spec.md](../../spec.md) 第 6 节全部验收条目，且现有 `POST /api/agent/runs` 默认行为（`dispatch_policy="reject"`）与既有 `AgentRun` 取消链路测试全部通过。
