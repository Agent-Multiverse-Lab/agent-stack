# Repository Agent Guide

`AGENTS.md` 是代理进入本仓库后的最小入口。详细规则、系统架构和能力合同都放在
`docs/`，本文件只负责说明当前项目和加载顺序。

`CLAUDE.md` 直接导入本文件。

## 1. 当前项目描述

`agent-stack` 是一个面向技术学习和工程实践的多 Agent 系统：

- 后端是 FastAPI，使用 LangChain/LangGraph 组织 Agent 执行。
- PostgreSQL 保存业务持久化状态；Redis/ARQ 负责队列、运行信号和事件流。
- RustFS 保存文件和解析产物，Milvus 承载知识检索向量。
- CubeSandbox 提供独立的工具和代码执行隔离，部署配置位于 `docker/cube/`。
- `gateway/` 提供 Go gRPC 卫星影像目录和 PostGIS 空间检索。
- `web/` 是 React/TypeScript 前端，负责 API 消费、页面状态和展示。

当前目录职责、依赖方向和数据所有权见
[docs/architecture/overview.md](docs/architecture/overview.md)。

## 2. 可加载的文档

以下是可读取文档，按当前任务类型按需读取，不读取与当前任务无关的文档：

1. 读取 [docs/working-rules.md](docs/working-rules.md)，加载当前仓库级开发规则。
2. 读取 [docs/architecture/README.md](docs/architecture/README.md)，确定承载该任务的系统。
3. 读取对应的 `docs/architecture/<system>-system.md`，各个具体模块职责和边界。
4. 任务涉及 `web/` 的页面、组件、目录、命名、样式或交互时，读取
   [docs/frontend/README.md](docs/frontend/README.md)。
5. 读取 [docs/spec/README.md](docs/spec/README.md)，再读取对应 domain README 和 capability 的
   `spec.md`；需要设计或实施时，只读取该 capability 根目录当前的 `plan.md` 和 `tasks.md`。
   如果 `plan.md` 路由到 `implementation/`，只继续读取当前任务对应的实施切片。`history/`
   默认不加载，只有追溯已完成变更时才读取指定版本。
6. 需要启动、迁移或验证时，读取 [docs/development.md](docs/development.md)。
7. 需要提交或发起 Pull Request 时，读取 [docs/contributing.md](docs/contributing.md)。
8. 只有任务涉及已有技术取舍时，才读取 [docs/adr/README.md](docs/adr/README.md) 和相关 ADR。

## 3. 能力路由

| 任务范围 | 先读取 |
| --- | --- |
| Agent 构造、上下文、子代理 | `docs/architecture/agent-system.md`、`docs/spec/agent/` |
| Run 生命周期、取消、事件流 | `docs/architecture/run-system.md`、`docs/spec/run/` |
| 知识上传、解析、索引、检索 | `docs/architecture/knowledge-system.md`、`docs/spec/knowledge/` |
| 状态和存储所有权 | `docs/architecture/persistence-system.md`、`docs/spec/persistence/` |
| 认证和用户身份 | `docs/architecture/auth-system.md` |
| 沙箱和工具隔离 | `docs/architecture/sandbox-system.md` |
| 卫星影像目录和多源检索 | `docs/architecture/data-platform-system.md`、`docs/spec/data-platform/` |
| 跨系统拓扑和目录职责 | `docs/architecture/overview.md` |
| Web 页面、组件、目录、命名、样式和交互 | `docs/frontend/README.md` |
| 产品身份和跨页面体验 | `docs/spec/product/` |
| 本地启动、迁移和验证 | `docs/development.md` |
| Pull Request 和 Git 提交 | `docs/contributing.md` |