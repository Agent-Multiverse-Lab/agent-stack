# Context Management Spec

## 1. Invariant

每次 Run 在 Service 入口合并一次配置快照，并将它显式传给 Agent：

1. Context 声明的配置默认值。
2. SQL `agent.agent_config` 中的角色配置。
3. 当前 Run 明确选择的模型及受信任的运行身份。

用户消息进入 Graph State，不将整份消息 metadata 或 Run metadata 混入 Context。
本能力不替代 Run 生命周期、数据库连接或模型凭据管理。

## 2. Requirements

### AG-CONT-001：显式来源与覆盖顺序

Worker 从持久化 AgentRun、用户和输入消息构造执行参数；Run 的身份字段覆盖 metadata 同名值。
Service 深拷贝 SQL 配置，模型优先级为：非空 Run 选择 > 非空 SQL 预设 > 应用默认模型。
`uid`、`run_id`、`thread_id`、`request_id` 和子 Run 的 `parent_run_id` 来自本次执行参数。
SQL 预设中的运行身份和未知 Context 字段由 Agent 构造入口拒绝。
应用默认模型在入口或 Context 默认值中确定，构图和摘要中间件只消费 `context.model`。
平台连接、凭据和存储根目录属于基础设施配置，不作为当前用户或 Run 身份的隐式来源。

### AG-CONT-002：单次运行快照

同一 Run 不重新查询角色配置或热更新 Context；数据库变更在后续 Run 生效。
SQL 中的嵌套配置在合并时深拷贝，修改一个 Run 的快照不污染 SQL 默认值或另一个 Run。
Resume 是新的 Run，通过相同的合并入口组装自己的 Context，再读取原会话的 checkpoint。

### AG-CONT-003：可追踪的组装与消费

`server/worker.py:process_agent_run()` 组装 runtime_metadata 和消息。
`server/service/thread_service.py:_build_agent_runtime_context()` 是 chat、subagent、resume 共用的合并入口，
由 `stream_agent_response()` 和 `resume_agent_response()` 调用。
`BaseAgent` 用显式传入的快照构造具体 Context；LeaderAgent、SubAgentGraph 和 Middleware 消费它。
子代理中间件只使用显式的父 Context 传递父 Run 身份，子 Run 通过自身角色 slug 获取独立配置。
Context 不负责修改数据库中的 Run 状态。

## 3. Acceptance

- Run 身份不会被 SQL 预设或未筛选的 metadata 覆盖。
- 非空模型选择按上述顺序生效，空字符串不会清除 SQL 预设。
- 全局默认模型在快照构造后改变，不影响已有快照；构图与摘要使用同一个模型值。
- 嵌套配置在不同 Run 之间隔离；普通执行、子 Run 和 Resume 的 Context 入口均可追踪。
