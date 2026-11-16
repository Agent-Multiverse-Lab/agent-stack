# 实施切片：前端策略提交与等待区交互

## 1. 请求与类型定义

目标：`web/src/api/agent-run.ts`、`web/src/api/chat.ts`。

- `AgentRunCreateRequest` 增加可选字段 `dispatch_policy?: "reject" | "queue" | "steer"`（默认不传或按交互模式指定）。
- 解析 `POST /api/agent/runs` 的两种成功响应：
  - HTTP 200：`run_id` 非空，立即建立 `GET /api/agent/runs/{run_id}/events` SSE 连接。
  - HTTP 202：`status === "queued"`、`run_id === null`，将返回条目写入会话等待区状态。
- 新增删除等待区请求 API：`cancelQueuedAgentRunRequest(requestId)` -> `DELETE /api/agent/runs/requests/{requestId}`。
- `ThreadDetailResponse` 类型增加 `queued_requests`。

## 2. 会话钩子与等待区状态流转

目标：`web/src/pages/chat/hooks/useAgentRun.ts` 及聊天输入/等待区组件。

- 会话空闲时直接提交并挂载 SSE；会话忙碌时根据用户选择以 `queue` 或 `steer` 提交并展示在输入区上方的等待列表（支持点击删除调用 `DELETE /api/agent/runs/requests/{requestId}`）。
- 若删除返回 409 且携带 `run_id`（与后端晋升并发），前端同步刷新线程详情或提示取消当前已启动的 Run。
- 当当前活跃 SSE 收到 `end` 事件后，前端按现有流程重新拉取 `GET /api/chat/thread/{thread_id}`：若后端已完成晋升，`ThreadDetailResponse.active_run` 会自动携带新 `run_id`，`useAgentRun` 自动挂载新 SSE 流，同时 `queued_requests` 同步移除已晋升条目。
