# Agent Construction Spec

## 1. 目标与边界

`AgentLibrary` 用于描述 Agent 的角色属性，包括名称、描述、Prompt 和 Context 预设参数。
属性模型定义在 `src/agents/agent_library/__init__.py` 中，每个角色在自己的文件中声明属性配置。
子角色文件位于 `agent_library/subagents/`，以角色命名，例如 `search.py`、`citation.py`。
这些预设仅用于启动时确保 SQL 中存在对应 Agent：缺失时按预设创建，已存在则保持原样。
运行时读取数据库配置；执行实现按 `backend_id` 选择，每次 Run 直接实例化 Agent class。
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
角色文件保存该角色的初始预设属性；包入口仅导入和汇总属性配置，供启动时补齐缺失记录。
预设不是已有数据库记录的配置来源，也不承担执行类查找或实例管理。
运行时 Service、Leader 和子 Agent Middleware 不依赖 AgentLibrary，也不将 SQL 记录转换为它。

### AG-CON-002：SQL 注册和读取

定义身份由唯一 `slug` 标识；多个子 Agent 的 `backend_id` 可以相同，统一为 `SubAgentGraph`。
`backend_id` 等于执行实体类的类名，只支持 `LeaderAgent` 和 `SubAgentGraph`，
SQL 不序列化 Python class 对象。角色 `slug` 用于查询记录，Backend ID 用于解析执行类。
基础信息写入现有 `agent` 列，`context` 写入 `agent.agent_config`。
`agent.is_subagent` 是非空布尔字段，数据库默认值为 `false`。
主 Agent 为 `false`，子 Agent 为 `true`；创建时按 `role == 'subagent'` 写入。
已有数据通过 schema 迁移按 `role` 回填；启动初始化不修改已有记录的标记。
Worker 启动按 slug 确保预定义 Agent 存在：缺失时插入初始属性，已存在时跳过。
跳过时保留全部字段，包括名称、描述、backend、角色标记、Context 配置、可见性、启用状态和时间戳。
重复启动或多个 Worker 同时初始化不会覆盖已有配置，也不会产生相同 slug 的重复记录。
运行时使用 SQL 中的有效角色配置，遵守已有启用状态和 Run 类型检查。

### AG-CON-003：统一子 Agent 构图

`SubAgentGraph(BaseAgent)` 在 `buildin/subagents/subagent_graph.py` 中实现 `get_agent(context)`，
统一装配模型、工具和 Middleware。所有子 Agent 使用 `SubAgentContext`。
Leader 使用自己的 `get_agent(context)`，通过构造参数接收数据库中的名称、描述和可用子角色列表。
子角色列表是仅包含 `slug`、`name`、`description` 的普通字典；Middleware 用它展示和定位角色。
该列表不持有 ORM 实例或运行配置，子 Run 的配置在执行时通过角色 slug 读取。
现有专业工具、验证和结果表达方式的取舍必须在删除专业实现前明确。

### AG-CON-004：每次 Run 创建实例

普通执行、子 Run 和 Resume 在现有 Service 执行入口查询角色记录，
统一通过 `agent.get_agent_class(record.backend_id)` 取得执行类，再创建本次 Run 的实例。
这里 `agent` 是 `src.agents.buildin` 模块；返回类型为 `type[BaseAgent]`。
Service 直接校验 SQL 中的角色标记和 `agent_config`，拒绝未知 Context 字段和预设 Run 身份。
`BaseAgent` 的执行协议、checkpointer 和 store 接口继续使用。
每次 Run 创建独立执行实例、Context 和绑定该 Context 的 Middleware。
Context 预设配置在使用前复制；运行身份来自当前 Run，显式模型选择覆盖预设模型，
缺省模型选择不以空字符串覆盖定义默认值。

### AG-CON-005：统一执行类解析

定义清单替代反射发现；现有 SQL repository 提供 Agent 查询；现有执行入口承接实例创建。
`src/agents/buildin/__init__.py` 的 `get_agent_class(backend_id)` 是唯一类解析入口，
Service 和 Worker 均通过它取得 `BaseAgent` 子类；调用方不再维护自己的类映射。
执行类映射集中在同一模块的 `AGENT_CLASSES` 常量字典中，函数从该字典按 Backend ID 取类。
函数仅按 Backend ID 精确匹配实体类名，未知值报错；角色 slug、`is_subagent` 和
`AgentLibrary` 不参与类解析。`is_subagent` 用于角色标记、数据一致性校验和构造参数选择。
替换完成后删除 `AgentManager`、实例缓存和其导出与调用，不新增承担相同职责的管理器。
公开 Agent 列表只包含启用且公开的 orchestrator，响应结构保持不变。

## 3. 验收

- 两个专业 slug 可以映射同一个 `SubAgentGraph`，各自 Prompt 和预设配置正确生效。
- 同一定义的两次 Run 使用不同实例，修改一份运行配置不污染定义或其他 Run。
- 启动时补齐缺失的主 Agent 和子 Agent，初始属性与预设一致。
- 重复启动保留已有记录的全部字段，包括手动修改的属性及禁用状态；不自动修正旧 backend。
- 新增 Agent 时正确保存 `is_subagent`；迁移覆盖启用和禁用角色，字段不接受 NULL。
- 普通执行和 Resume 都通过 SQL 选择实现，每次创建实例；公开列表保持内部角色不可见。
- 仅存在于数据库中的角色可以运行；Leader 名称、描述和可用子角色以 SQL 为准，不构造 AgentLibrary。
- 委派仍走已有子 Run/ARQ 路径，保留 `run_type=subagent` 与 `parent_run_id`。
- 实施后的业务代码和测试没有 AgentManager 或已删除专业 Agent class 的引用。
