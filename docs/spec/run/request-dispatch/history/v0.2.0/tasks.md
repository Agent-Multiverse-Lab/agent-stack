# Agent Run 分发策略与前端等待区任务

## 持久化与接口

- [x] 为 `AgentRunRequest` 移除冗余 `conversation_id` 列并保留索引化 `thread_id`（无外键），新增 `dispatch_policy`、`status`、`queue_seq` 字段与部分索引 `ix_agent_run_request_thread_queued`，编写 Alembic 迁移。
- [x] 在 `AgentRunRequestRepository` 移除 `create_request` 的 `conversation_id` 参数，并实现 `has_queued_steer_for_thread`、`has_expired_steer_for_run`、`pop_next_queued_for_thread`、`mark_dispatched`。
- [x] 调整 `ConversationRepository` 会话历史查询过滤 `Message.status != "queued"`。
- [x] 更新 `create_agent_run_service` 支持 `enqueue`（默认等待，忙碌入队返回 202 且不中断当前 Run）、`reject`（忙碌不落盘直接 409）与 `steer`（入转向队列返回 202，不写额外队列信号）。

## 运行时与 Steer 调度

- [x] 实现 `SteerStopMiddleware`（`before_model(can_jump_to=["end"])`）并接入 `LeaderAgent`，在检测到当前会话存在 `status == "queued"` 且 `dispatch_policy == "steer"` 的 `AgentRunRequest` 时跳转 `END`。
- [x] 更新 `server/worker.py`：识别 Turn 边界转向退出并写回 Run 终态，在 `_finalize_run` 与租约过期回收收敛终态后调用 `dispatch_next_queued_request` 晋升并执行 `enqueue_agent_run`。

## 消息保存收敛

- [x] 更新 `server/service/thread_service.py`：异常/取消收敛先执行 `save_message_from_langgraph_state` 同步已提交 checkpoint。
- [x] 统一未进 checkpoint 的 `accumulated_msg` 收敛逻辑，优先 reconcile 已有 `model_audit` 行；为 `resume_agent_response` 补传 `full_msg`。
- [x] 为 Turn 边界 `steer` 退出保留 `stop_reason` 元数据，保证前端准确展示工具已完成但回答被转向的状态。

## 前端等待区与验证

- [x] 在 `ChatPage.tsx` 实现前端未发送等待区队列（`queuedSubmissions`），支持 0 延迟删除、一键 `Steer` 强制插入与当前 Run 完成后自动发送。
- [x] 补充策略分发、Turn 边界 `jump_to="end"`、`save` 收敛与前端等待区的单元与集成测试，完成编译、Lint 与迁移验证。

## 验证记录

- PostgreSQL 独立 schema：23 项通过，覆盖策略接收、幂等、FIFO、并发晋升/撤销、输入历史分页、宽限超时撤销、迁移往返。
- 后端消息保存、真实 LangGraph 工具轮次、硬取消、Worker 与审计回归：93 项通过。
- 聊天页面、Composer、Hook、切流与 API 回归：92 项通过。
- 后端 compileall、修改文件 Ruff/ESLint、TypeScript 检查通过。
- 前端构建成功，产物位于 `/tmp/agent-stack-request-dispatch-dist`。默认 `web/dist/assets` 存在文件系统权限问题。
- 本机数据库已应用并确认 `0031_request_dispatch_queue (head)`。
- 全量前端检查已执行：Lint 的两个既有错误位于 `ArtifactCard.tsx`、`ChunksPanel.tsx`；知识库页面的 17 个测试因缺少 `listKnowledgeTasks` 等 API mock 失败。本次修改的聊天测试已通过。
