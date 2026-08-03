# Agent

Agent 是系统的推理和任务编排部分。当前运行时由一个顶层 `LeaderAgent` 组织工具和内部
Sub-agent，内部 Agent 只承担边界清晰的子任务。

## 运行链路

```text
AgentManager
  -> 解析顶层 Agent / Sub-agent
  -> thread_service 选择运行实例
  -> BaseAgent.stream_messages_with_event(...)
  -> LeaderAgent.get_agent(context)
  -> MCP Tools + Middleware + Sub-agent Tools
  -> LangGraph Agent 执行并返回事件
```

- `src/agents/manager.py::AgentManager` 扫描 Agent 包，分别记录公开的顶层 Agent 和内部
  Sub-agent；`get_agent(agent_id)` 返回进程内实例。
- `server/service/thread_service.py::stream_agent_response` 组合
  `uid`、`run_id`、`thread_id`、`request_id`，再调用统一流式入口。
- `src/agents/base_agent.py::BaseAgent.stream_messages_with_event` 根据 `agent_context` 创建
  Context，调用
  `get_agent(context)`，并把 `messages`、`values`、工具执行事件向 Worker 输出。
- `src/agents/leaderagent/agent.py::LeaderAgent.get_agent` 先按 `context.mcps` 加载 MCP Tools，
  再由 `_build_agent(runtime_context, tools)` 组装 LangGraph Agent。

## LeaderAgent 的 Middleware 编排

`LeaderAgent._create_middlewares(context)` 当前按以下顺序组装：

| 顺序 | 文件 / 类 | 作用 | 关键参数 |
| --- | --- | --- | --- |
| 1 | `src/agents/backends/composite_backend.py::create_custom_filesystem_middleware` | 提供 `/skill/`、`/memory/`、`/workspace/` 虚拟路径，并把默认路径交给 Sandbox Backend | `context`、`tool_token_limit_before_evict` |
| 2 | `src/agents/middlewares/subagent_middlware.py::SubAgentMiddleware` | 把模型工具调用转换为子 Agent Run | `subagents`、`parent_context`、`system_prompt` |
| 3 | `PatchToolCallsMiddleware` | 修正工具调用消息形态 | 无 |
| 4 | `ModelRetryMiddleware` | 模型失败后最多重试 3 次，失败继续向后处理 | `max_retries=3`、`on_failure="continue"` |
| 5 | `ToolRetryMiddleware` | 工具失败后最多重试 5 次 | `max_retries=5` |
| 6 | `TodoListMiddleware` | 维护任务清单和执行进度 | 无 |

这个顺序体现了“先准备运行能力，再提供委派工具，最后处理模型、工具和任务状态”的编排
方式。MCP 是动态工具来源，Sub-agent 是受控的异步任务来源，二者都由 LeaderAgent 统一
决定是否使用。

## Sub-agent 编排策略

`SubAgentMiddleware` 通过 `description` 和 `subagent_slug` 限定任务边界，并把父运行的
`run_id`、`uid`、`request_id` 传给子运行。模型可使用四种节奏不同的工具：

| 工具 | 参数 | 使用场景 |
| --- | --- | --- |
| `task` | `description`、`subagent_slug` | 后续步骤立即依赖结果，启动后等待最终文本 |
| `subagent_start` | `description`、`subagent_slug` | 长任务或可并行任务，只返回子 `run_id` |
| `subagent_status` | `run_id` | 查询状态、最近进度和已完成结果 |
| `subagent_cancel` / `subagent_await` | `run_id` | 取消后台任务，或等待并取得最终文本 |

编排规则是：简单任务由 LeaderAgent 直接完成；确实能拆分的任务才委派；并行任务使用
`subagent_start`，有依赖的任务使用 `task`；子 Agent 只返回自己的结果，不替代 LeaderAgent
整合最终回答。

当前注册的内部 Agent 是：

- `src/agents/subagents/searchagent/agent.py::SearchAgent`：使用
  `knowledge_search`、`web_search_parallel`、`web_search_one` 做证据检索和综合。
- `src/agents/subagents/outlineagent/agent.py::OutlineAgent`：不带工具，输出结构化大纲。

## Context 示例

| 文件 / 类 | 主要参数 |
| --- | --- |
| `src/agents/base_context.py::BaseContext` | `system_prompt`、`uid`、`thread_id`、`run_id`、`request_id`、`model`、`skill_root`、`mcps` |
| `src/agents/leaderagent/context.py::LeaderAgentContext` | 继承 `BaseContext`，增加 `sub_model`、`fallback_model`、`image_model` |
| `src/agents/subagents/searchagent/context.py::SearchAgentContext` | 继承 `BaseContext`，增加 `sub_model` |
| `src/agents/subagents/outlineagent/context.py::OutlineAgentContext` | 继承 `BaseContext`，提供 `system_prompt` 和 `model` |

Context 是 Middleware、Tools 和 Sub-agent 读取运行参数的共同入口；消息正文属于本次调用
输入，不与运行配置混在一起。
