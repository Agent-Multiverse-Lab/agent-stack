# Tasks: Run Event Streaming

## Task Map

| Task ID | 关联需求 | 主要文件 | 说明 |
| --- | --- | --- | --- |
| ES-001 | RUN-ES-001 | `server/service/agent_run_service.py` | 删除旧 event builder 和无调用的发布包装 |
| ES-002 | RUN-ES-002/004 | `server/service/agent_run_service.py` | 按 envelope 读取进度，并根据 PostgreSQL 终态生成公共 end |
| ES-003 | RUN-ES-003 | `server/utils/agent_run_utils.py` | 将完整 envelope 格式化为现有 SSE frame |
| ES-004 | RUN-ES-005 | `server/service/arq_queue_servcie.py`, `server/worker.py` | 三个 writer 统一使用 `payload` 参数，并接入普通写入与 end 写入调用点 |
| ES-005 | RUN-ES-001/003/005 | `test/test_agent_run_service.py`, `test/test_worker_stream_event_smoother.py` | 验证唯一 builder、payload 读取、SSE 契约与 Worker 参数转发 |
| ES-006 | RUN-ES-001/003/005 | `AGENTS.md` | 同步 envelope、Worker writer 与 SSE formatter 职责边界 |
| ES-007 | RUN-ES-004 | `server/service/agent_run_service.py` | 每轮先重查 PostgreSQL，排空普通事件后生成唯一公共 end |
| ES-008 | RUN-ES-004/005 | `test/test_agent_run_service.py` | 验证 Redis end 只唤醒重查及 Agent Stream 前的数据库终止路径 |
| ES-009 | RUN-ES-006 | `src/agents/base_agent.py`, `server/service/thread_service.py` | 统一 v3 messages/values/tools channel 和公开 payload 投影 |
| ES-010 | RUN-ES-006 | `server/worker.py` | 将内部 chunk 分类映射为五种 Run event type，messages 只写标准 item |
| ES-011 | RUN-ES-007 | `server/router/agent_router.py`, `server/service/agent_run_service.py` | 用 Last-Event-ID 从 Redis Stream ID 之后续读 |
| ES-012 | RUN-ES-008 | `web/src/types/chat.ts`, `web/src/api/chat.ts` | 定义 AgentRunEvent/AgentMessage 并逐帧解析 SSE id/event/data |
| ES-013 | RUN-ES-008/009 | `web/src/composables/useChat.ts`, `web/src/views/ChatView.vue`, `web/src/components/chat/ChatLoadingStateComponent.vue` | 归并并渲染消息、Run 状态、Agent state 和工具执行事件；等待组件复用于 Thread Detail 读取和 Run 等待，拥有像素波、经过时间和动画降级，当前 Run 有可见 Assistant 文本或 Agent tool 状态后卸载 |
| ES-014 | RUN-ES-006/007/008/009 | `test/`, `web/` | 验证 channel 投影、cursor 续读、判别联合和前端构建 |

## Done 条件

- `agent_run_service.py` 不再构造或发布 Agent Run 消息。
- Redis envelope 只由 `arq_queue_servcie.py` 构造。
- SSE formatter 无数据库和 Redis 依赖。
- Redis `event_type=end` 只唤醒 PostgreSQL 状态重查，不直接结束 SSE。
- PostgreSQL 已终态且普通事件排空后，SSE 生成唯一 `data.type=end` 并结束。
- PostgreSQL 驱动生成的公共终态不会重复写入 Redis。
- 队列 writer 与 Worker 两个 writer 对事件体统一使用 `payload` 参数。
- Worker 的两个 writer 只做 payload 转发与 `end` 类型固定，不增加其他副作用。
- Run 创建响应与历史消息 Run 元数据提供 `run_type`，Redis entry 不重复该字段。
- Redis 与前端只使用 `status/messages/values/agent_execute_event/end` 五种事件类型。
- `messages.items` 符合 `AgentMessage`，不包含原始 chunk 或 LangChain metadata。
- 前端逐帧处理完整 `AgentRunEvent`，只按外层 `type` 路由。
- `ChatLoadingStateComponent` 只在当前 Run 活跃且尚无可见 Assistant 文本或 Agent tool 状态时显示，并在卸载时清理计时器。
- 当前 Run 的 Thinking 与 Agent tool 状态互斥，任一 tool 消息可见时不显示 Thinking。
- SSE `id:` 作为不透明 `event_id` 被保存并通过 `Last-Event-ID` 续读。
- 前后端不新增 `seq/sequential` 字段，前端不定义或读取 `ChunkStatus`。
- Agent channel 解析异常传播到 Worker，不会落成 `completed`。
