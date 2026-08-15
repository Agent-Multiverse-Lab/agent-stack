# System Overview

## 1. Purpose

说明 `multi-agent-s2c` 在运行时如何分层：  
Web/API -> Service -> Worker -> Agent Runtime -> Storage/RAG。

## 2. Domain Architecture

- **Agent Domain**：构建并编排多代理能力。
- **Run Domain**：从创建到终态的执行协调（队列、取消、事件）。
- **Knowledge Domain**：文件上传、解析、切块、索引、检索、重排。
- **Persistence Domain**：PostgreSQL / Redis / MinIO / Milvus 的状态与存储边界。
- **Sandbox Domain**：外部能力执行隔离边界。

## 3. High-level Topology

```text
Web/UI
  -> FastAPI Router
     -> Service Layer
        -> PostgreSQL Repositories
        -> Redis/ARQ
           -> ARQ Worker (process_agent_run)
              -> Agent Runtime / SubAgent Middleware
                 -> Redis Stream Events
```

## 4. Data Ownership

- PostgreSQL: 用户、会话、消息、Run 及知识基础数据。
- Redis: ARQ 队列、运行信号与 `run:events:{run_id}` 流。
- MinIO: 知识文件和解析产物。
- Milvus: 向量索引数据。

## 5. Cross-domain Rules

- Service 只编排流程，不持有 Agent 核心策略。
- Agent 不直接读写业务数据库，必须通过 Service/Repository 入口。
- Worker 只做执行，不直接承担 API 请求调度。

## 6. Architecture Invariants

- `run` 生命周期终态一致性由数据库主导。
- 取消信号必须可中断可收敛，最终写入持久化终态。
- 运行时事件按 `append-only` 写入 Redis Stream。
