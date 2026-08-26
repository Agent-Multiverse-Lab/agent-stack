# System Overview

## 1. Purpose

说明 `agent-stack` 在运行时如何分层：
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

## 6. Source Ownership Map

| 目录 | 承载能力 | 不承载 |
| --- | --- | --- |
| `server/router/` | HTTP 鉴权入口、参数校验、响应整形 | SQL、Agent 推理、基础设施客户端构造 |
| `server/service/` | 跨仓储和基础设施的业务编排 | Agent 核心策略、页面状态 |
| `server/worker.py` | ARQ Worker 生命周期和 Run 执行 | API 请求调度、前端连接生命周期 |
| `src/agents/` | Agent、SubAgent、工具和中间件装配 | HTTP、数据库、队列、对象存储流程 |
| `src/knowledge/` | Parser、Extractor、Chunker、Embedding、检索 | Run 终态和 HTTP 编排 |
| `src/database/` | SQLAlchemy 模型、会话和责任命名的仓储 | Redis Stream 或 Agent 推理 |
| `src/storage/` | MinIO、Redis/ARQ 的基础设施适配 | Run 生命周期业务语义 |
| `src/configs/` | 类型化配置、环境解析、默认值和校验 | 业务编排和可变运行时状态 |
| `src/model/` | Provider-neutral 的 Chat、Embedding、Reranker 构造 | 数据库或向量库查询 |
| `src/third_party/` | 外部 SDK 的小型兼容边界 | 应用策略和通用业务工具 |
| `src/utils/` | 跨子系统复用的无状态通用帮助函数 | 单一子系统的领域逻辑 |
| `sandbox_server/` | 独立沙箱管理和执行隔离 | 应用持久化和 Agent Run 编排 |
| `web/` | API 消费、页面状态和展示 | 后端领域规则 |
| `docker/` | Dockerfile 和 Compose 拓扑 | 应用业务逻辑 |
| `migrate/` | Alembic 环境和有序 schema revision | 启动、Worker、Agent 和业务 seed |
| `scripts/` | 有明确输入和可观察结果的维护入口 | import-time 副作用 |
| `test/` | 确定性单元、契约测试和明确命名的 demo | 默认套件中的 live network 依赖 |

## 7. Document Ownership

- 稳定的全局原则：[`docs/constitution.md`](../constitution.md)。
- 系统拓扑和模块所有权：本目录。
- 能力行为、合同和验收：[`docs/spec/`](../spec/README.md)。
- 长期技术取舍：[`docs/adr/`](../adr/README.md)。
- 源码只实现并验证上述文档，不反向复制完整架构说明。

## 8. Architecture Invariants

- `run` 生命周期终态一致性由数据库主导。
- 取消信号必须可中断可收敛，最终写入持久化终态。
- 运行时事件按 `append-only` 写入 Redis Stream。
