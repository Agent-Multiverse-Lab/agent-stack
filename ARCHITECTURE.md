# ARCHITECTURE.md

本文档是 `agent-stack` 的代码地图，只描述相对稳定的系统边界、目录职责、核心运行链路与架构不变量，用于帮助判断“改动应该落在哪里”。具体表结构、接口协议与实现细节以真实源码、Schema、Compose 和测试为准。

## 鸟瞰

`agent-stack` 是基于 FastAPI、LangChain/LangGraph 和 React 的多智能体平台。前端通过 `/api` 调用 FastAPI，后端服务层协调 PostgreSQL、Redis/ARQ、RustFS、Milvus、Neo4j 与 CubeSandbox：

```text
Web/UI
  -> FastAPI Router
     -> Service Layer
        -> PostgreSQL Repositories
        -> Redis / ARQ
           -> ARQ Worker
              -> Agent Runtime (LeaderAgent / SubAgents)
                 -> Knowledge / CubeSandbox / MCP
                 -> Redis Stream Events -> SSE
```

## 后端代码地图

| 目录 / 文件 | 承载职责 |
| --- | --- |
| `server/main.py`、`server/lifespan.py` | FastAPI 应用构造、路由注册与 API 进程生命周期管理 |
| `server/router/` | HTTP 鉴权入口、参数校验与响应整形 |
| `server/service/` | 跨仓储和基础设施的业务编排，以及 ARQ 队列、事件流协作 |
| `server/worker.py` | 独立 ARQ Worker 生命周期与 Run 执行入口 |
| `src/agents/` | `LeaderAgent`、共享子代理执行图、角色预设、工具、中间件与运行后端适配 |
| `src/model/` | 平台级 Chat / Embedding / Rerank 供应商配置、目录缓存与单次运行时构造 |
| `src/knowledge/` | 文件解析、切块、向量化、图谱抽取、索引与检索重排 |
| `src/database/` | SQLAlchemy 模型、数据库会话与仓储 |
| `src/storage/` | RustFS、Redis/ARQ 等基础设施客户端适配 |
| `src/configs/` | 类型化配置、环境解析与校验 |
| `src/utils/` | 跨子系统复用的通用辅助函数 |
| `src/third_party/` | 外部 SDK 的小型兼容边界 |
| `migrate/` | Alembic 数据库迁移与有序 schema revision |
| `docker/cube/` | CubeSandbox 部署配置、主机预检与运行验收 |

## 前端代码地图

前端是 React + TypeScript + Vite 应用，业务入口集中在 `web/src/`（详见 [web/AGENTS.md](web/AGENTS.md) 与 [设计规范](docs/develop-guides/design.md)）：

- `app/`：应用根组件、路由与登录守卫。
- `api/`：后端 HTTP / SSE 接口封装与协议类型。
- `context/`：跨页面共享状态。
- `layouts/`：布局及其专用组件。
- `pages/<feature>/`：路由页面及其专用组件、Hooks 和类型。
- `components/ui/`：shadcn/ui（Base UI）基础组件与共享视觉变体，不放业务逻辑。
- `components/common/`：跨页面复用的产品组件。
- `styles/index.css`、`types/`、`lib/`：全局主题 token、共享类型与通用工具。

## 核心域与运行链路

- **Agent**：`LeaderAgent` 统一编排工具与子代理；子角色通过配置与上下文复用共享子代理执行图，经由 Run 系统委派与追踪，不直接读写业务数据库或队列。
- **Run**：管理对话与子任务的异步执行生命周期（排队、转向 `steer`、取消、`ask_user` 中断与 `resume` 恢复）；同一时刻一个 Run 仅由单一持有有效租约的 Worker 执行，终态单向收敛（`completed` / `failed` / `cancelled` / `interrupted`）。
- **Model**：平台级 Chat / Embedding / Rerank 供应商配置存于 PostgreSQL，Redis 缓存可重建的已启用脱敏目录；采用显式 `provider_id:model_id` 选型并校验可用性，不做静默降级，Run 执行消费冻结快照。
- **Knowledge**：负责文件上传、解析、切块、向量化、图谱抽取与检索重排；每个知识库显式绑定 Embedding 模型与维度；聊天附件与知识库文件分属独立边界。
- **Sandbox**：工具与代码执行隔离在独立 CubeSandbox MicroVM 中，应用通过用户级实例发现与连接交互，业务库不持久化沙箱实例 ID，主流程不依赖沙箱本地状态决策终态。
- **Auth**：邮箱密码登录与 JWT 身份识别；平台管理权限由部署配置 `ADMIN_EMAILS` 在后端路由依赖处独立校验。

## 架构不变量与存储分工

- **PostgreSQL 是业务状态唯一真相**：承载用户、会话、消息、Run 与执行租约、模型配置与知识元数据；所有状态转移与终态收敛以数据库事务为准。
- **Run 通过 ARQ Worker 异步执行**：长耗时 Agent 执行脱离 FastAPI 请求线程，由独立 Worker 进程并发消费、续租和收敛终态。
- **Redis / Redis Stream 仅作运行时通道**：承载 ARQ 队列、取消信号、append-only 事件流（支撑 SSE 断线重连）及可重建的已启用模型目录缓存，不承接状态真相。
- **RustFS / Milvus / Neo4j 各司其职**：RustFS 保存原始上传文件与解析产物；Milvus 保存知识分块与实体向量；Neo4j 保存知识图谱节点与关系。
- **独立 CubeSandbox 隔离执行面**：API/Worker 不持有 Docker Socket，沙箱故障通过标准错误回到主流程，不污染 Run 状态机。
- **后端是最终权限边界**：路由鉴权与资源归属校验在后端依赖与仓储查询处执行，前端守卫只负责界面体验。
