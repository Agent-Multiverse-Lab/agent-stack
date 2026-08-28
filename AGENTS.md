# Repository Agent Guide

`AGENTS.md` 是代理进入本仓库后的最小入口。详细规则、系统架构和能力合同都放在
`docs/`，本文件只负责说明当前项目和加载顺序。

`CLAUDE.md` 直接导入本文件。

## 1. 当前项目描述

`agent-stack` 是一个面向技术学习和工程实践的多 Agent 系统：

- 后端是 FastAPI，使用 LangChain/LangGraph 组织 Agent 执行。
- PostgreSQL 保存业务持久化状态；Redis/ARQ 负责队列、运行信号和事件流。
- MinIO 保存文件和解析产物，Milvus 承载知识检索向量。
- `sandbox_server/` 提供独立的工具和代码执行隔离。
- `web/` 是 Vue/TypeScript 前端，负责 API 消费、页面状态和展示。

当前目录职责、依赖方向和数据所有权见
[docs/architecture/overview.md](docs/architecture/overview.md)。

## 2. 文档加载顺序

按任务范围按需读取，不扫描与当前任务无关的全部文档：

1. 读取 [docs/working-rules.md](docs/working-rules.md)，加载仓库级开发规则。
2. 读取 [docs/architecture/README.md](docs/architecture/README.md)，确定承载该任务的系统。
3. 读取对应的 `docs/architecture/<system>-system.md`，确认模块职责和边界。
4. 读取 [docs/spec/README.md](docs/spec/README.md)，再读取对应 domain README 和 capability 的
   `spec.md`；需要设计或实施时，只读取该 capability 根目录当前的 `plan.md` 和 `tasks.md`。
   如果 `plan.md` 路由到 `implementation/`，只继续读取当前任务对应的实施切片。`history/`
   默认不加载，只有追溯已完成变更时才读取指定版本。
5. 需要启动、迁移或验证时，读取 [docs/development.md](docs/development.md)。
6. 需要提交或发起 Pull Request 时，读取 [docs/contributing.md](docs/contributing.md)。
7. 只有任务涉及已有技术取舍时，才读取 [docs/adr/README.md](docs/adr/README.md) 和相关 ADR。

## 3. 能力路由

| 任务范围 | 先读取 |
| --- | --- |
| Agent 构造、上下文、子代理 | `docs/architecture/agent-system.md`、`docs/spec/agent/` |
| Run 生命周期、取消、事件流 | `docs/architecture/run-system.md`、`docs/spec/run/` |
| 知识上传、解析、索引、检索 | `docs/architecture/knowledge-system.md`、`docs/spec/knowledge/` |
| 状态和存储所有权 | `docs/architecture/persistence-system.md`、`docs/spec/persistence/` |
| 认证和用户身份 | `docs/architecture/auth-system.md` |
| 沙箱和工具隔离 | `docs/architecture/sandbox-system.md` |
| 跨系统拓扑和目录职责 | `docs/architecture/overview.md` |
| 产品身份和跨页面体验 | `docs/spec/product/` |
| 本地启动、迁移和验证 | `docs/development.md` |
| Pull Request 和 Git 提交 | `docs/contributing.md` |

架构文档回答“哪个系统承载什么”；spec 文档回答“能力必须如何工作”；源码负责实现和验证，
不要把这些详细规则重新复制回 `AGENTS.md`，也不要递归扫描整个 `docs/spec/`。
