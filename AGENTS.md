# Repository Agent Guide

`AGENTS.md` 是代理进入本仓库后的渐进式入口；`CLAUDE.md` 直接导入本文件。具体表结构、接口、依赖和命令以源码、Schema、Compose 与测试为准。

## 项目概览

`agent-stack` 是一个面向技术学习和工程实践的多 Agent 系统：

- 后端是 FastAPI，使用 LangChain/LangGraph 组织 Agent 执行。
- PostgreSQL 保存业务持久化状态；Redis/ARQ 负责队列、运行信号和事件流。
- RustFS 保存文件和解析产物，Milvus 承载知识检索向量，Neo4j 保存知识图谱。
- CubeSandbox 提供独立的工具和代码执行隔离，部署配置位于 `docker/cube/`。
- `web/` 是 React/TypeScript 前端，负责 API 消费、页面状态和展示。

## 按需加载文档

只按当前任务范围读取对应入口，不加载与当前任务无关的文档：

| 任务范围 | 先读取 |
| --- | --- |
| 系统拓扑、代码地图与架构不变量 | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Web 前端目录、组件、样式与验证 | [web/AGENTS.md](web/AGENTS.md)、[docs/develop-guides/design.md](docs/develop-guides/design.md) |
| 编写或维护文档 | [docs/AGENTS.md](docs/AGENTS.md)、[docs/develop-guides/documentation-guidelines.md](docs/develop-guides/documentation-guidelines.md) |
| 非平凡改动的设计提案与决策记录 | [docs/develop-guides/decisions/README.md](docs/develop-guides/decisions/README.md) |
| 核心运行机制详解 | [docs/mechanisms/index.md](docs/mechanisms/index.md) |
| 本地启动、迁移、部署与验证命令 | [docs/develop-guides/development.md](docs/develop-guides/development.md) |
| Git 提交与 Pull Request 规范 | [CONTRIBUTING.md](CONTRIBUTING.md) |

## 工作原则

1. **直接与克制**：严格禁止因假设性或极低概率风险主动添加未要求的警告、免责声明、审批流程、冗余 fallback 或防御性校验；不写空洞保证、多层模糊修饰或与权责无关的反向范围说明。
2. **按需决策，不堆过程文档**：普通修复和明确的单点需求直接实现；改变持久状态、生命周期、权限边界、公开契约或引入新抽象/依赖的非平凡改动，在 `docs/develop-guides/decisions/proposed/` 写短提案，落地后迁至 `implemented/`；本地临时计划放在被 Git 忽略的 `docs/vibe/`。
3. **尊重边界与事实 Owner**：源码、Schema、Compose 与测试拥有可执行事实；移动或删除文件、调整模块所有权或修改公开契约前先说明影响并取得确认。
4. **子树规则叠加**：进入 `web/` 或 `docs/` 工作时同时遵循对应子树的 `AGENTS.md`，子树规则只补充本目录，不复制到根文件。
5. **验证如实报告**：只报告实际执行过的命令、测试与观察到的结果；仅修改文档时至少运行 `git diff --check`。
