# Persistence System Architecture

## 1. Responsibility

定义持久化真相与运行时缓存的分工边界。

行为规格入口：[State Ownership Spec](../spec/persistence/state-ownership/spec.md)。

## 2. Storage by Responsibility

### PostgreSQL (Source of Truth)
- `User / Agent / Conversation / Message / Attachment / AgentRunRequest / AgentRun / KnowledgeFile` 等业务状态。
- 平台级 `ModelProvider` 连接配置、启用状态和 Chat 模型清单。
- 卫星目录的 `Source / Collection / Scene / SceneAsset`；空间范围由 PostGIS 保存和索引。
- 状态变更要求事务可见、可幂等、可追溯。

### Redis
- ARQ 队列元数据、`run:cancel:{run_id}`（cancel signal）。
- `run:events:{run_id}`（可读事件流）。
- `model:chat:list:v3`：从 PostgreSQL 派生的全局已启用 Chat 模型脱敏列表。

### RustFS
- 原始上传文件、解析产物、Markdown 快照。
- 卫星栅格、波段、质量掩膜和预览对象；PostgreSQL 只保存对象引用。

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
| `SubAgentConversationRelation` | PostgreSQL | 父子 Agent 会话关系及其创建、软删除事实 |
| `Message.id` | PostgreSQL | 持久化消息标识 |
| `Message.content/image_content/msg_metadata` | PostgreSQL | 请求输入内容，通过 trigger_message_id 读取 |
| `Conversation.conversation_metadata` | PostgreSQL | 会话当前配置，创建 Run 时读取并保存为运行快照 |
| `AgentRunRequest.request_id` | PostgreSQL | 已接收请求的唯一标识，通过相同 request_id 关联 Run |
| `AgentRunRequest.trigger_message_id` | PostgreSQL | 已接收输入的 Message ID，Run 创建失败或忙碌时仍保留 |
| `AgentRun.trigger_message_id` | PostgreSQL | Worker 根据 Run 重建输入 |
| `AgentRun.run_type` | PostgreSQL | `chat` 或 `subagent` 执行类型 |
| `AgentRun.uid` | PostgreSQL | Run 创建时的用户归属快照，不以外键绑定 `User` 生命周期 |
| `AgentRun.created_by_run_id` | PostgreSQL | 创建来源：子任务的委派 Run，或 resume 的被恢复 Run |
| `AgentRun.agent_status` | PostgreSQL | Run 唯一生命周期字段 |
| `run:{run_id}` | ARQ | 后台任务 Job ID |
| `run:events:{run_id}` | Redis Stream | 事件传输和重连游标 |
| `run:cancel:{run_id}` | Redis | 运行时取消信号 |
| `ModelProvider` | PostgreSQL | 平台共享的模型连接、启用状态和模型选择 |
| `model:chat:list:v3` | Redis | `ModelProvider` 已启用 Chat 模型的可丢弃、可重建、不含连接参数的全局展示投影 |

Redis、内存、RustFS 和 Milvus 不得复制 PostgreSQL 的权威业务状态；如果新增副本，
必须先在对应能力文档中说明 Owner、生命周期、一致性和清理规则。
全局模型列表不是可独立修改的业务状态；缓存失效、损坏或过期时必须从 PostgreSQL 重建。
