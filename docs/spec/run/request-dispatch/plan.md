# Agent Run 分发策略与等待区调度计划

## 1. 当前任务

在现有 `AgentRunRequest` 两阶段提交与 `AgentRun` 并发门禁基础上，为 `POST /api/agent/runs` 引入 `dispatch_policy`（`reject` / `queue` / `steer`），实现基于 `AgentRunRequest` 的等待区队列、Waiting-Area 删除接口、Turn 边界 `before_model` `jump_to="end"` 优雅停机、非正常消息 `save` 收敛，以及 Run 终态后的自动晋升调度。

数据契约与流程图见 [spec.md](spec.md)，按职责拆分的实施切片位于 `implementation/`：

- 持久化与 API 契约：[implementation/persistence-and-api.md](implementation/persistence-and-api.md)
- 运行时 Steer 优雅停机与晋升：[implementation/runtime-steer-and-promotion.md](implementation/runtime-steer-and-promotion.md)
- 非正常消息 Save 收敛：[implementation/message-save-convergence.md](implementation/message-save-convergence.md)
- 前端策略提交与等待区交互：[implementation/frontend-queue-interaction.md](implementation/frontend-queue-interaction.md)

## 2. 任务目标

1. 为 `AgentRunCreateRequest` 与 `AgentRunRequest` 增加 `dispatch_policy`、等待区状态 `status` 与顺序号 `queue_seq`，保持 `AgentRun` 单活约束与 `enqueue_agent_run` 契约不变。
2. 支持 `reject`（忙碌拒收且不留脏消息）、`queue`（入等待区，当前 Run 终态后晋升）与 `steer`（入等待区并软停止当前 Run）三种策略。
3. 通过 LangGraph `before_model` middleware 的 `jump_to="end"` 实现 Turn 边界优雅停机，保证已执行 `tool_calls` 与 `ToolMessage` 完整闭合，保留 `_cancellable_stream` 硬取消作为兜底。
4. 统一非正常结束与正常结束的 `save` 路径：先 `save_message_from_langgraph_state` 同步已提交 checkpoint，再 reconcile 半截流式输出，补齐 `resume_agent_response` 的 `full_msg`。
5. 提供 `DELETE /api/agent/runs/requests/{request_id}` 与 `ThreadDetailResponse.queued_requests`，支持前端展示与撤销等待区请求。

## 3. 如何修改

1. **持久化与接口层**：移除 `AgentRunRequest` 冗余的 `conversation_id` 列（以 `thread_id` 索引逻辑关联会话，不建外键），扩展 `dispatch_policy`、`status`、`queue_seq` 与 Alembic 迁移；更新 `AgentRunRequestRepository` 与 `AgentRunRequestInput` 支持入队、按 `queue_seq` 出队与取消；调整 `create_agent_run_service` 在会话行锁下按策略路由，新增 `cancel_queued_agent_run_request_service` 与删除路由，扩展 `ThreadDetailResponse`。
2. **运行时与调度层**：在 `LeaderAgent` 装配 `SteerStopMiddleware`（`before_model(can_jump_to=["end"])`），直接查询当前 `thread_id` 下是否存在 `status == "queued"` 且 `dispatch_policy == "steer"` 的 `AgentRunRequest`，不向 Redis 写入额外转向信号；在 `server/worker.py` 的 `_finalize_run` 终态提交后及租约回收器收敛后调用 `dispatch_next_queued_request(thread_id)` 晋升下一条等待请求并调用 `enqueue_agent_run`。
3. **消息保存层**：重构 `server/service/thread_service.py` 的终止保存顺序，令 `CancelledError` / 异常 / `steer` 停机先同步 checkpoint，再统一 reconcile 未入 checkpoint 的 `accumulated_msg`，避免重复插消息与审计行残留。
4. **前端交互层**：更新 `web/src/api/agent-run.ts`、`web/src/api/chat.ts` 与 `useAgentRun`，支持 `202 queued` 响应解析、等待区队列展示、撤销排队请求以及活跃 Run 终态后重拉 `ThreadDetailResponse` 自动挂载新 `active_run` SSE。

## 4. 实施步骤（计划）

1. 完成数据库迁移与 `AgentRunRequestRepository` 等待区方法，调整 `Message` 在 `queued` 态的线程详情过滤。
2. 更新 `create_agent_run_service` 与 `agent_router.py`，落地 `reject` / `queue` / `steer` 路由与 `DELETE /api/agent/runs/requests/{request_id}`。
3. 落地 `SteerStopMiddleware`（基于 `AgentRunRequest` 状态检查并在 `before_model` 跳 `END`）及 Worker 终态后的 `dispatch_next_queued_request` 晋升逻辑。
4. 重构 `thread_service.py` 的非正常消息 `save` 收敛并修复 `resume_agent_response` 缺失 `full_msg`。
5. 接入前端 `dispatch_policy` 参数、等待区条目展示与删除操作。
6. 补充单元测试与集成测试（策略路由、并发删除/晋升互斥、Turn 边界 `jump_to="end"`、`save` 收敛），执行迁移与检查。

## 5. 验收标准

- 遵循 [spec.md](spec.md) 第 6 节全部验收条目，且现有 `POST /api/agent/runs` 默认行为（`dispatch_policy="reject"`）与既有 `AgentRun` 取消链路测试全部通过。
