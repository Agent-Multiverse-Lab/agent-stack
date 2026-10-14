# Chat 模型选择

## 1. Purpose

在 Chat 输入区提供平台统一的模型选择。模型目录从全局 `model_provider` 已启用记录投影，
并通过全局 Redis read-through cache 提供；缓存只优化读取，不成为配置真相。

## 2. Requirements

### CHAT-MODEL-001 Canonical catalog

PostgreSQL 全局 `model_provider` 记录是目录的权威来源。只投影 `is_enabled=true` 的供应商及其
`enabled_models`；供应商按 `provider_id` 稳定排序，单个供应商内保留管理员保存的模型顺序。每个目录项包含：

- `id`：`provider/model`；
- `name`：原始模型名称；
- `display_name`：模型家族缩写，例如 `Qwen`；
- `version`：用于输入区展示的型号版本；
- `provider` 与 `icon`；
- `is_available`：当前 ChatModel loader 是否支持该 Provider；
- 现有的 `is_default / is_fallback / is_flash` 标记。

`id` 暂时保持既有 Run 合同，不切换为 Provider Management 内部解析使用的冒号格式。若当前静态 loader
无法用同一个 `provider/model` ID 构造模型，包括未知 provider 或不兼容的含斜杠 model ID，目录项仍可展示，
但 `is_available=false`，前端不可选择。

顶层继续返回 `default_model`、`fallback_model`、`flash_model`、`image_model` 和 `models`。
系统配置的默认模型存在于全局目录且可执行时保留；否则 `default_model` 取第一个可执行模型，
没有可执行模型时为空字符串。其他角色只在其配置值存在于全局可执行目录时保留，否则为空字符串；
模型项角色标记与顶层最终值一致。本轮不新增平台默认模型数据库字段。

### CHAT-MODEL-002 Redis read-through cache

`GET /api/models` 要求用户登录，读取全局 Redis key `model:catalog:v3`。cache miss、过期或完整结构
校验失败时从 PostgreSQL 重建目录，
写入一小时 TTL 后返回；Redis 不可用时直接返回本次数据库投影。

管理员的供应商写事务提交成功后先删除全局目录，再从已提交数据重建；事务回滚不刷新缓存。
FastAPI 启动补齐全局预置后预热一次；用户注册不触碰目录，预热失败不影响已提交数据库或 API 可用性。
目录不得包含 API Key、base URL、额外请求头、请求体覆盖、`has_api_key`、客户端对象或 ORM 数据。
Settings 列表与详情不从该目录读取。

### CHAT-MODEL-003 Composer selector

`ModelSelector` 内嵌于 `AgentMessageComposer` 操作区，使用现有 shadcn DropdownMenu。
触发器展示当前模型的 `display_name`，菜单项展示名称以及 provider/version；目录中的每个模型最多出现一次。
`is_available=false` 的模型保留可见但禁用，不能通过鼠标或键盘选中。没有模型时显示原位空状态，
没有可执行模型时禁用触发器，不回退前端硬编码选项。
菜单沿用现有键盘、Esc、外部点击和焦点行为；hover 高亮与选中态分离并尊重减少动画设置。
Run 活跃、模型目录加载中或 Composer 被禁用时不可切换模型。

### CHAT-MODEL-004 Run integration

创建对话时，选中的模型 ID 写入 `Conversation.conversation_metadata.model`；未指定时由后端选择
Agent 配置中的模型，Agent 也未指定时读取应用默认模型。创建普通 Run 时，显式选择更新会话绑定，
未指定则沿用绑定，旧会话没有绑定时依次沿用 Agent 配置和应用默认模型；解析结果写入单次 Run metadata。
Worker 重载 Run 后把该快照传入
`BaseContext.model`，Leader Agent 使用该模型构造当前 Run 的 ChatModel。后端拒绝不在当前
全局可用模型目录中的 model ID；目录中暂不可执行的模型只展示且不可选择。
当前阶段 Agent 仍使用现行静态 loader 的连接参数，不读取 Provider 中保存的
Base URL、API Key 或额外请求头。

### CHAT-MODEL-005 State boundary

模型目录与输入区选择由 `ModelContext` 管理，不写入 `localStorage`。
模型绑定持久化在已有 Conversation metadata JSON 中；打开或刷新对话时从详情 metadata 恢复选择，
新对话使用输入区当前选择。认证 token 变化时先清空目录与选择，旧账号的迟到响应不得写入新账号 Context。

## 3. Non-goals

- 不缓存 LLM 推理响应、Embedding、Rerank 结果或 LangChain 模型对象。
- 不把 Redis 当作供应商配置或凭据真相。
- 不在本轮把 Provider 连接配置注入 Agent runtime，也不迁移历史 Run 的模型 ID。

## 4. Acceptance Criteria

- `/api/models` 返回全局已启用模型及可直接渲染的名称、版本和 icon 标识。
- `/api/models` 在 cache hit 时返回全局 Redis 目录，在 miss/损坏时从 PostgreSQL 重建并回填。
- 所有登录用户得到相同目录和默认值，响应不含任何连接参数或凭据。
- 输入区能够选择真实模型，且运行期间不可切换。
- 所选模型进入当前 Run 的 Agent context。
- 后端单测和前端 ESLint、TypeScript、生产构建通过。
