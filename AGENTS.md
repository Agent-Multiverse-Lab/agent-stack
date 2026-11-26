# Repository Agent Guide

`AGENTS.md` 是代理进入本仓库后的最小入口。详细规则、系统边界与进行中的功能设计放在 `docs/`，具体实现以源码为准。

`CLAUDE.md` 直接导入本文件。

## 1. 当前项目描述

`agent-stack` 是一个面向技术学习和工程实践的多 Agent 系统：

- 后端是 FastAPI，使用 LangChain/LangGraph 组织 Agent 执行。
- PostgreSQL 保存业务持久化状态；Redis/ARQ 负责队列、运行信号和事件流。
- RustFS 保存文件和解析产物，Milvus 承载知识检索向量。
- CubeSandbox 提供独立的工具和代码执行隔离，部署配置位于 `docker/cube/`。
- `web/` 是 React/TypeScript 前端，负责 API 消费、页面状态和展示。

当前目录职责、依赖方向和数据所有权见
[docs/architecture/overview.md](docs/architecture/overview.md)。

## 2. 可加载的文档

以下是可读取文档，按当前任务类型按需读取，不读取与当前任务无关的文档：

1. 读取 [docs/working-rules.md](docs/working-rules.md)，加载当前仓库级开发规则。
2. 读取 [docs/architecture/README.md](docs/architecture/README.md) 与对应的
   `docs/architecture/<system>-system.md`，明确系统边界和长期不变量后，直接读取真实源码。
3. 任务涉及 `web/` 的页面、组件、目录、命名、样式或交互时，读取
   [docs/frontend/README.md](docs/frontend/README.md)。
4. 若当前任务在 `docs/develop/` 下存在对应的单文件设计稿，按需读取了解方向和关键取舍。
5. 需要启动、迁移或验证时，读取 [docs/development.md](docs/development.md)。
6. 需要提交或发起 Pull Request 时，读取 [docs/contributing.md](docs/contributing.md)。
7. 只有任务涉及已有技术取舍时，才读取 [docs/adr/README.md](docs/adr/README.md) 和相关 ADR。

## 3. 能力路由

| 任务范围 | 先读取 |
| --- | --- |
| Agent 构造、上下文、子代理 | `docs/architecture/agent-system.md` |
| Run 生命周期、取消、事件流、排队派发 | `docs/architecture/run-system.md` |
| 知识上传、解析、索引、检索 | `docs/architecture/knowledge-system.md` |
| 状态和存储所有权 | `docs/architecture/persistence-system.md` |
| 认证和用户身份 | `docs/architecture/auth-system.md` |
| 沙箱和工具隔离 | `docs/architecture/sandbox-system.md` |
| 模型供应商预置、平台配置和目录缓存 | `docs/architecture/model-system.md` |
| 跨系统拓扑和目录职责 | `docs/architecture/overview.md` |
| Web 页面、组件、目录、命名、样式、品牌与交互 | `docs/frontend/README.md` |
| 进行中的单文件功能设计 | `docs/develop/` |
| 本地启动、迁移和验证 | `docs/development.md` |
| Pull Request 和 Git 提交 | `docs/contributing.md` |
