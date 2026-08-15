# Agent System Architecture

## 1. Responsibility

负责将上下文转为可执行的代理图，统一入口是 `LeaderAgent`，并通过中间件连接子代理与工具。

## 2. Core Components

- `src/agents/base_agent.py`：agent 执行基类。
- `src/agents/base_context.py`：运行上下文模型。
- `src/agents/leaderagent/`：主编排 Agent。
- `src/agents/subagents/*`：内部子代理能力。
- `src/agents/middlewares/subagent_middlware.py`：子代理调度与结果等待。
- `src/agents/backends/*`：外部运行后端（沙箱、模型适配器）。

## 3. Context Rule

agent 运行上下文只来自：

1. 配置项（配置模块）
2. run 触发时上下文（参数 + 消息）
3. 数据库加载的参数（如 agent 配置）

上下文不从外部全局状态隐式拉取。

## 4. Sub-agent Rule

- 子代理只通过中间件被 `LeaderAgent` 调用。
- 子代理生命周期仍使用同一 `AgentRun` 机制追踪。
- 子代理结果返回给父流程，不直接绕过 run 系统。

## 5. Runtime Boundary

- agent 层仅负责调用策略与工具。
- 与 run、仓储、队列相关的状态变更一律在 server service/repository 层完成。
