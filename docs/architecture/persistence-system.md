# Persistence System Architecture

## 1. Responsibility

定义持久化真相与运行时缓存的分工边界。

## 2. Storage by Responsibility

### PostgreSQL (Source of Truth)
- `User / Conversation / Message / AgentRun / KnowledgeFile` 等业务状态。
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
