# Agent Run 分发策略与等待区调度任务

## 持久化与接口

- [ ] 为 `AgentRunRequest` 移除冗余 `conversation_id` 列并保留索引化 `thread_id`（无外键），新增 `dispatch_policy`、`status`、`queue_seq` 字段与部分索引 `ix_agent_run_request_thread_queued`，编写 Alembic 迁移。
- [ ] 在 `AgentRunRequestRepository` 移除 `create_request` 的 `conversation_id` 参数，并实现 `list_queued_for_thread`、`has_queued_steer_for_thread`、`pop_next_queued_for_thread`、`mark_dispatched`、`cancel_queued_request`。
- [ ] 调整 `ConversationRepository` 会话历史查询过滤 `Message.status == "queued"`，在 `ThreadDetailResponse` 暴露 `queued_requests`。
- [ ] 更新 `create_agent_run_service` 支持 `reject`（忙碌不落盘直接 409）、`queue`（入等待区返回 202）与 `steer`（入等待区返回 202，不写额外队列信号）。
- [ ] 新增 `DELETE /api/agent/runs/requests/{request_id}`，在会话锁下移除 `queued` 请求或对已晋升请求返回 409 + `run_id`。

## 运行时与 Steer 调度

- [ ] 实现 `SteerStopMiddleware`（`before_model(can_jump_to=["end"])`）并接入 `LeaderAgent`，在检测到当前会话存在 `status == "queued"` 且 `dispatch_policy == "steer"` 的 `AgentRunRequest` 时跳转 `END`。
- [ ] 更新 `server/worker.py`：识别 Turn 边界转向退出并写回 Run 终态，在 `_finalize_run` 与租约过期回收收敛终态后调用 `dispatch_next_queued_request` 晋升并执行 `enqueue_agent_run`。

## 消息保存收敛

- [ ] 更新 `server/service/thread_service.py`：异常/取消收敛先执行 `save_message_from_langgraph_state` 同步已提交 checkpoint。
- [ ] 统一未进 checkpoint 的 `accumulated_msg` 收敛逻辑，优先 reconcile 已有 `model_audit` 行；为 `resume_agent_response` 补传 `full_msg`。
- [ ] 为 Turn 边界 `steer` 退出保留 `stop_reason` 元数据，保证前端准确展示工具已完成但回答被转向的状态。

## 前端与验证

- [ ] 更新 `web/` 的 Run 请求类型、等待区列表渲染、删除排队请求交互与终态切流逻辑。
- [ ] 补充策略分发、并发晋升/删除竞争、Turn 边界 `jump_to="end"`、`save` 收敛的单元与集成测试，完成编译、Lint 与迁移验证。
