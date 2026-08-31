<!-- markdownlint-disable MD033 MD041 -->

<div align="center">

<img src="web/src/assets/logo.svg" alt="AM logo" width="64">

# agent-stack

🤖 通用多智能体系统，面向智能体编排、交互与应用开发。

A general-purpose multi-agent system for agent orchestration, interaction, and application development.

</div>

## 🎯 项目定位

本仓库是用于技术学习与工程实践的阶段性项目。第一阶段聚焦 Web 应用形态，构建类似
ChatGPT 的交互体验，并验证多智能体编排、任务协作与工具调用等核心能力。

后续阶段将依次探索以下产品形态：

1. 命令行工具（CLI），提供终端环境中的任务执行与自动化能力。
2. Coding Agent，面向代码理解、生成、修改与工程协作场景。
3. 桌面级应用，整合本地资源、工作区与更完整的交互能力。

项目将在上述形态演进的基础上，持续扩展智能体协作、知识检索、工具调用、内容生成、
任务自动化及其他通用能力。

## 🛠️ 主要技术栈

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

## 🖼️ 界面预览

### 聊天主界面

![agent-stack 聊天主界面](./docs/frontend-main.png)

### 登录界面

![agent-stack 登录界面](./docs/frontend-home.png)

## 🏗️ 系统架构

<div align="center">

![agent-stack 系统架构图](./docs/image.png)

</div>

### 后端总体架构

```mermaid
flowchart TB
    Web[Web] -->|HTTP / SSE| API[FastAPI API]

    subgraph Backend[后端系统]
        API --> RunService[Run Service]
        RunService --> Worker[Run Worker]
        Worker --> Context[组装本次 Run Context]
        Context --> Leader[LeaderAgent]

        subgraph Runtime[Agent Runtime]
            Leader --> Prompt[系统 Prompt 与可用工具]
            Prompt --> Middleware[中间件链]
            Middleware --> Model[模型决策]
            Model --> Tool[工具执行]
            Tool --> Model
        end

        Middleware --> Delegation[SubAgent Middleware]
        Delegation --> ChildRun[独立 SubAgent Run]
        ChildRun --> Specialized[专项 Agent]
        Specialized --> Delegation

        Model --> Result[Agent 输出]
        Result --> Worker
        Worker --> RunService
    end
```

前端只通过 HTTP 发起请求，并通过 SSE 接收运行输出。后端负责 Run 编排、运行上下文组装、
Agent 执行、工具调用和子 Agent 委派。

### LeaderAgent 中间件

```mermaid
flowchart LR
    Request[模型请求] --> SubAgent[SubAgent 委派]
    SubAgent --> Patch[工具调用修补]
    Patch --> ModelRetry[模型失败重试]
    ModelRetry --> ToolRetry[工具失败重试]
    ToolRetry --> Todo[任务规划]
    Todo --> Model[模型]

    Compression[上下文压缩 / 摘要<br/>规划能力，尚未接入] -.-> Request
```

中间件在模型与工具调用周围提供委派、修补、重试和任务规划能力。上下文压缩与摘要已有设计方向，
但当前尚未接入 `LeaderAgent` 中间件链。

### SubAgent Middleware

```mermaid
flowchart TB
    Leader[LeaderAgent] --> Choose{委派方式}

    Choose -->|task| Sync[启动子 Run<br/>等待最终结果]
    Choose -->|subagent_start| Async[后台启动子 Run<br/>立即返回 run_id]

    Async --> Status[subagent_status<br/>查询状态与最近进度]
    Async --> Await[subagent_await<br/>等待最终结果]
    Async --> Cancel[subagent_cancel<br/>请求取消]

    Sync --> Result[标准化子 Agent 结果]
    Await --> Result
    Status --> Leader
    Cancel --> Leader
    Result --> Leader
```

`SubAgentMiddleware` 把 LeaderAgent 的工具调用转换为独立的子 Run，并始终校验子 Run 属于当前父 Run。
专项 Agent 只返回有界结果，由 LeaderAgent 继续整合，不绕过父流程直接产生最终答案。

### 后端 Run 执行链路

```mermaid
sequenceDiagram
    participant Web as Vue Web
    participant API as FastAPI
    participant Run as Run Service
    participant Worker as Run Worker
    participant Agent as LeaderAgent
    participant MW as Middleware Chain
    participant Sub as SubAgent

    Web->>API: POST /agent/runs
    API->>Run: 创建 Run
    API-->>Web: run_id
    Web->>API: 连接 Run SSE
    Run->>Worker: 执行 run_id
    Worker->>Agent: 执行顶层 Agent
    Agent->>MW: 处理模型与工具调用
    opt 需要委派子任务
        MW->>Run: 创建 Child Run
        Run->>Sub: 执行专项 Agent
        Sub-->>MW: 进度或最终结果
    end
    MW-->>Agent: 模型结果
    Agent-->>Worker: Agent 输出
    Worker-->>Run: 收口 Run 结果
    Run-->>API: 运行事件与终态
    API-->>Web: SSE 输出 / end
```

## 📖 文档

- [系统架构与模块边界](docs/architecture/README.md)
- [能力规格](docs/spec/README.md)
- [本地开发、启动与验证](docs/development.md)
- [数据库迁移样例](migrate/README.md)
- [贡献与提交规范](CONTRIBUTING.md)
