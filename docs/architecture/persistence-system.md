# Persistence System Architecture

## 1. Responsibility

定义持久化真相与运行时缓存的分工边界。

行为规格入口：[State Ownership Spec](../spec/persistence/state-ownership/spec.md)。

## 2. Storage by Responsibility

### PostgreSQL (Source of Truth)
- `User / Agent / Conversation / Message / Attachment / AgentRun / KnowledgeFile` 等业务状态。
- 状态变更要求事务可见、可幂等、可追溯。

### Redis
- ARQ 队列元数据、`run:cancel:{run_id}`（cancel signal）。
- `run:events:{run_id}`（可读事件流）。

### MinIO
- 原始上传文件、解析产物、Markdown 快照。

### Milvus
- 知识检索向量与元数据。

## 3. Anti-pattern

不得将运行结果状态转移交给 Redis Stream 回填数据库；不得将 DB 状态当作事件推送目标。

## 4. Operational Notes

- Redis key 与 stream 均带 TTL，避免无界增长。
- PostgreSQL 事务失败要可回滚并保持 run 状态可重试。

## 5. Identifier and State Ownership

| 标识或状态 | 权威承载 | 说明 |
| --- | --- | --- |
| `Conversation.id` | PostgreSQL | 数据库主键 |
| `Conversation.thread_id` | PostgreSQL | 对外会话/运行时标识 |
| `Message.id` | PostgreSQL | 持久化消息标识 |
| `AgentRun.trigger_message_id` | PostgreSQL | Worker 根据 Run 重建输入 |
| `AgentRun.run_type` | PostgreSQL | `chat` 或 `subagent` 执行类型 |
| `AgentRun.parent_run_id` | PostgreSQL | 父子 Run 关系，不是类型标记 |
| `AgentRun.agent_status` | PostgreSQL | Run 唯一生命周期字段 |
| `run:{run_id}` | ARQ | 后台任务 Job ID |
| `run:events:{run_id}` | Redis Stream | 事件传输和重连游标 |
| `run:cancel:{run_id}` | Redis | 运行时取消信号 |

Redis、内存、MinIO 和 Milvus 不得复制 PostgreSQL 的权威业务状态；如果新增副本，
必须先在对应能力文档中说明 Owner、生命周期、一致性和清理规则。
