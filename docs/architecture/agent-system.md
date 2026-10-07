# Agent System Architecture

## 1. Responsibility

负责将上下文转为可执行的代理图，统一入口是 `LeaderAgent`，并通过中间件连接子代理与工具。

行为规格入口：

- [Context Management Spec](../spec/agent/context-management/spec.md)
- [Subagent Delegation Spec](../spec/agent/subagent-delegation/spec.md)
- [Agent Construction Spec](../spec/agent/agent-construction/spec.md)

## 2. Core Components

- `src/agents/base_agent.py`：agent 执行基类。
- `src/agents/base_context.py`：运行上下文模型。
- `src/agents/leaderagent/`：主编排 Agent。
- `src/agents/agent_library/`：角色配置实体与按角色文件声明的预设。
- `src/agents/subagents/subagentgraph.py`、`subagent_context.py`：所有子角色共用的执行图和 Context。
- `src/agents/middlewares/subagent_middlware.py`：子代理调度与结果等待。
- `src/agents/backends/*`：外部运行后端（沙箱、模型适配器）。

## 3. Context Rule

agent 运行上下文只来自：

1. 配置项（配置模块）
2. run 触发时上下文（参数 + 消息）
3. 数据库加载的参数（如 agent 配置）

上下文不从外部全局状态隐式拉取。

上下文能力由 `src/agents/base_context.py` 和具体 Agent/SubAgent context 承载；
`server/service/` 或 Worker 在执行入口组装运行时值，再通过方法契约传入 Agent。
消息等单次调用数据属于 Graph State，不属于平行的运行配置来源。

## 4. Sub-agent Rule

- 子代理只通过中间件被 `LeaderAgent` 调用。
- 子代理生命周期仍使用同一 `AgentRun` 机制追踪。
- 子代理结果返回给父流程，不直接绕过 run 系统。

## 5. Runtime Boundary

- agent 层仅负责调用策略与工具。
- 与 run、仓储、队列相关的状态变更一律在 server service/repository 层完成。

## 6. Capability Ownership

| 能力 | 承载位置 | 责任边界 |
| --- | --- | --- |
| Agent 公共执行协议 | `src/agents/base_agent.py` | 暴露 Agent 执行和消息/事件流接口，不处理业务持久化 |
| 上下文管理 | `src/agents/base_context.py`、具体 context | 合并并校验本次 Run 配置，不读取隐式全局运行状态 |
| 顶层编排 | `src/agents/leaderagent/` | 编排工具和内部 Agent，保持基础 Prompt 领域中立 |
| 子代理委派 | `src/agents/middlewares/subagent_middlware.py`、`server/service/` | 通过 Run-backed 工具创建和等待子 Run，不嵌入父图执行 |
| 子角色定义 | `src/agents/agent_library/subagents/` | 声明 slug、名称、描述、backend 和 Context 预设 |
| 子角色执行 | `src/agents/subagents/` | 共用 SubAgentGraph 与 SubAgentContext，不成为新的 HTTP/Run 编排入口 |
| 模型、工具和后端装配 | LeaderAgent、SubAgentGraph、`src/model/`、Agent backend | 在 Agent 边界组装；数据库、队列和对象存储仍由外层拥有 |

`AgentLibrary` 只持有可序列化的角色配置，不持有执行实例。Worker 启动按 slug 同步 SQL，
保留记录身份和 enabled 运维设置；公开列表由 SQL 查询启用且公开的 orchestrator。
普通执行、子 Run 和 Resume 在 `thread_service._build_agent_runtime()` 中按 SQL backend_id
直接实例化 `LeaderAgent` 或 `SubAgentGraph`；每次 Run 使用新的实例、Context 和 Middleware。
Leader 接收可用子角色定义，Middleware 通过 slug 创建并入队子 Run。

所有子角色共用知识/网络检索、Gateway 目录和 MCP 工具，以及沙箱、文件系统、图片校验和模型重试
Middleware。专业 Prompt、报告 Schema 和预设参数放在角色文件；工具是否用于当前任务由角色规则约束。
Gateway 工具仍通过 Python gRPC 客户端访问目录，不直接连接 PostgreSQL/PostGIS 或 RustFS。
`src/knowledge/tools.py` 承接知识和网络检索工具。
`src/agents/middlewares/image_validation_middleware.py` 检查 MCP 工具可用性并反馈调用错误；
对 MCP 返回的内嵌单帧图片执行有界解码、格式和完整性检查。URL/路径/资产 ID 的文件内容及图像语义
正确性不视为已验证。图片角色通过 Context 预设要求 MCP 可用。

## 7. Implementation Invariants

- 每个子角色在 `agent_library/subagents/` 的对应文件声明 AgentLibrary 实体；
  共享构造放在 SubAgentGraph，不为角色创建专业 Agent class 或独立 builder。
- 内部 Agent 的现有位置只有在明确批准的结构重构中才能移动，
  不为未来想法创建空模块。
- `BaseAgent.stream_messages(...)` 使用 LangGraph `astream(...)`；事件流入口使用
  `astream_events(version="v3")` 并转发 `messages` channel 的 `params.data`。
- `LeaderAgent` 的基础 Prompt 保持领域中立；专业行为放在工具、内部 Agent 或运行上下文。
- `search_agent` 只做有界查询规划、检索、来源比较和证据综合，并保持为
  `LeaderAgent` 的可选能力；`citation_agent` 只校验调用方提供的声明和来源。
- Agent 运行配置只有具体 context、当前 Run 提供的值和后端加载的值三类来源；
  不增加模块全局配置、中间件私有默认值或平行关键字参数。
