# Agent Construction Spec

## 1. 目标与边界

`AgentLibrary` 是直接表达角色配置的实体类，包括名称、描述、Prompt 和 Context 预设参数。
实体类定义在 `src/agents/agent_library/__init__.py` 中，每个角色在自己的文件中声明实体实例。
子角色文件位于 `agent_library/subagents/`，以角色命名，例如 `search.py`、`citation.py`。
这些配置通过 SQL 注册供运行时读取；执行实现按 `backend_id` 选择，每次 Run 直接实例化 Agent class。
Leader 保留自己的构图实现，所有子 Agent 使用同一个 `SubAgentGraph` 和 `SubAgentContext`。

本能力负责声明、注册和实例创建。上下文来源遵循
[Context Management](../context-management/spec.md)；子 Run 创建、入队、等待和取消遵循
[Subagent Delegation](../subagent-delegation/spec.md)。

所有子角色共用工具和 Middleware，由各自专业 Prompt 和 Context 预设约束角色行为。
定义编辑界面、Markdown 编译、定义版本系统不在本次范围。

## 2. 要求

### AG-CON-001：角色定义

`AgentLibrary` 包含 `slug`、`name`、`description`、`backend_id`、`context`。
`context` 保存可序列化的 Context 预设配置，Prompt 使用 `system_prompt` 字段。
定义不持有执行实例、编译后的 Graph、Tool/Middleware 对象或本次 Run 身份。
一个专业角色对应一个定义实例，子 Agent 的专业角色以这些配置表达。
角色文件保存该角色的全部预设属性；包入口仅导入和汇总实体供注册使用。

### AG-CON-002：SQL 注册和读取

定义身份由唯一 `slug` 标识；多个子 Agent 的 `backend_id` 可以相同，统一为 `SubAgentGraph`。
`backend_id` 保存受支持的 class 字符串标识，SQL 不序列化 Python class 对象。
基础信息写入现有 `agent` 列，`context` 写入 `agent.agent_config`。
Worker 启动按 slug 同步预定义角色配置，更新已有记录的声明字段；保留原主键和运维设置的 `enabled`。
运行时使用 SQL 中的有效角色配置，遵守已有启用状态和 Run 类型检查。

### AG-CON-003：统一子 Agent 构图

`SubAgentGraph(BaseAgent)` 在 `subagents/subagentgraph.py` 中实现 `get_agent(context)`，
统一装配模型、工具和 Middleware。所有子 Agent 使用 `SubAgentContext`。
Leader 使用自己的 `get_agent(context)`，通过构造参数接收可用子 Agent 定义。
子 Agent Middleware 使用定义的 slug、名称和描述表达可用角色。
现有专业工具、验证和结果表达方式的取舍必须在删除专业实现前明确。

### AG-CON-004：每次 Run 创建实例

普通执行、子 Run 和 Resume 在现有 service 执行入口按 `backend_id` 解析 class 并直接实例化。
`BaseAgent` 的执行协议、checkpointer 和 store 接口继续使用。
每次 Run 创建独立执行实例、Context 和绑定该 Context 的 Middleware。
Context 预设配置在使用前复制；运行身份来自当前 Run，显式模型选择覆盖预设模型，
缺省模型选择不以空字符串覆盖定义默认值。

### AG-CON-005：替换 AgentManager

定义清单替代反射发现；现有 SQL repository 提供 Agent 查询；现有执行入口承接实例创建。
`backend_id` 的 class 对应关系用执行入口中的显式字典表达。
替换完成后删除 `AgentManager`、实例缓存和其导出与调用，不新增承担相同职责的管理器。
公开 Agent 列表只包含启用且公开的 orchestrator，响应结构保持不变。

## 3. 验收

- 两个专业 slug 可以映射同一个 `SubAgentGraph`，各自 Prompt 和预设配置正确生效。
- 同一定义的两次 Run 使用不同实例，修改一份运行配置不污染定义或其他 Run。
- 现有子 Agent SQL 记录的旧 class 标识更新为 `SubAgentGraph`，主键、slug 和禁用状态保留。
- 普通执行和 Resume 都通过 SQL 选择实现，每次创建实例；公开列表保持内部角色不可见。
- 委派仍走已有子 Run/ARQ 路径，保留 `run_type=subagent` 与 `parent_run_id`。
- 实施后的业务代码和测试没有 AgentManager 或已删除专业 Agent class 的引用。
