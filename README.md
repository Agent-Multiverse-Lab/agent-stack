# multi-agent-s2c

A general-purpose multi-agent system for exploring agent orchestration, interaction, and application development. 面向智能体编排、交互与应用开发的通用多智能体系统。

## 项目定位

本仓库是用于技术学习与工程实践的阶段性项目，目前处于第一阶段。项目定位为通用多智能体系统。第一阶段聚焦 Web 应用形态，构建类似 ChatGPT 的交互体验，并验证多智能体编排、任务协作与工具调用等核心能力。

后续阶段将依次探索以下产品形态：

1. 命令行工具（CLI），提供终端环境中的任务执行与自动化能力。
2. Coding Agent，面向代码理解、生成、修改与工程协作场景。
3. 桌面级应用，整合本地资源、工作区与更完整的交互能力。

项目将在上述形态演进的基础上，持续扩展智能体协作、知识检索、工具调用、内容生成、任务自动化及其他通用能力。

## 主要技术栈

| 领域 | 技术 |
| --- | --- |
| 后端服务 | Python 3.13、FastAPI、Pydantic、Uvicorn |
| 智能体与工作流 | LangChain、LangGraph、Deep Agents |
| 数据持久化 | PostgreSQL、SQLAlchemy、Alembic |
| 异步任务与事件流 | Redis、ARQ、Server-Sent Events（SSE） |
| 知识与文件存储 | Milvus、MinIO |
| 模型与工具集成 | OpenAI-compatible API、MCP、A2A、Tavily |
| Web 前端 | Vue 3、TypeScript、Vite 7、Vue Router 4 |
| 工程与部署 | uv、Docker Compose、Ruff |

## 系统架构

![multi-agent-s2c 系统架构图](./docs/image.png)

## 数据库迁移样例

仓库当前只提供不包含真实 Schema 变更的 Alembic 迁移样例。目录边界和
`upgrade()`、`downgrade()` 使用方式见 [`migrate/README.md`](./migrate/README.md)。

## Contributing

See commit and PR conventions in [CONTRIBUTING.md](./CONTRIBUTING.md).
