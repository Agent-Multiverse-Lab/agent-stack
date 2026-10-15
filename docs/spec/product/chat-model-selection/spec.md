# Chat 模型选择

## 1. Purpose

在 Chat 输入区提供平台统一的模型选择。模型列表从全局 `model_provider` 已启用记录投影，
并通过全局 Redis read-through cache 提供；缓存只优化读取，不成为配置真相。

## 2. Requirements

### CHAT-MODEL-001 Canonical model list

PostgreSQL 全局 `model_provider` 记录是模型列表的权威来源。只投影 `is_enabled=true` 的供应商及其
`enabled_models`；供应商按 `provider_id` 稳定排序，单个供应商内保留管理员保存的模型顺序。每个模型项包含：

- `id`：`provider/model`；
- `name`：原始模型名称；
- `display_name`：模型家族缩写，例如 `Qwen`；
- `version`：用于输入区展示的型号版本；
- `provider` 与 `icon`；
- `is_available`：当前 ChatModel loader 是否支持该 Provider；
- 现有的 `is_default / is_fallback / is_flash` 标记。

`id` 是模型选择、Conversation、Run 和 Provider 运行时解析的唯一格式。解析只切分第一个 `/`，
因此模型 ID 自身可以包含后续 `/` 或 `:`。协议工厂无法构造的模型仍可展示，但
`is_available=false`，前端不可选择。

顶层继续返回 `default_model`、`fallback_model`、`flash_model`、`image_model` 和 `models`。
系统配置的默认模型存在于全局模型列表且可执行时保留；否则 `default_model` 取第一个可执行模型，
没有可执行模型时为空字符串。其他角色只在其配置值存在于全局可执行目录时保留，否则为空字符串；
模型项角色标记与顶层最终值一致。本轮不新增平台默认模型数据库字段。

### CHAT-MODEL-002 Redis read-through cache

`GET /api/models` 要求用户登录，读取全局 Redis key `model:chat:list:v3`。cache miss、过期或完整结构
校验失败时从 PostgreSQL 重建模型列表，
写入一小时 TTL 后返回；Redis 不可用时直接返回本次数据库投影。

管理员的供应商写事务提交成功后先删除全局模型列表，再从已提交数据重建；事务回滚不刷新缓存。
FastAPI 启动补齐全局预置后预热一次；用户注册不触碰目录，预热失败不影响已提交数据库或 API 可用性。
模型列表不得包含 API Key、base URL、额外请求头、请求体覆盖、`has_api_key`、客户端对象或 ORM 数据。
Settings 列表与详情不从该缓存读取。

### CHAT-MODEL-003 Composer selector

`ModelSelector` 内嵌于 `AgentMessageComposer` 操作区，使用现有 shadcn DropdownMenu。
触发器展示当前模型的 `display_name`，菜单项展示名称以及 provider/version；列表中的每个模型最多出现一次。
`is_available=false` 的模型保留可见但禁用，不能通过鼠标或键盘选中。没有模型时显示原位空状态，
没有可执行模型时禁用触发器，不回退前端硬编码选项。
菜单沿用现有键盘、Esc、外部点击和焦点行为；hover 高亮与选中态分离并尊重减少动画设置。
Run 活跃、模型目录加载中或 Composer 被禁用时不可切换模型。

### CHAT-MODEL-004 Run integration

创建对话时，选中的模型 ID 写入 `Conversation.conversation_metadata.model`；未指定时由后端选择
Agent 配置中的模型，Agent 也未指定时读取应用默认模型。创建普通 Run 时，显式选择更新会话绑定，
未指定则沿用绑定，旧会话没有绑定时依次沿用 Agent 配置和应用默认模型；解析结果写入单次 Run metadata。
后端在持久化前从 PostgreSQL 校验 model ID。Worker 重载 Run 后按快照解析 `ModelConnection`，
通过协议工厂构造当前 Run 的 ChatModel，并把模型 ID 写入 `BaseContext.model` 用于追踪。
Provider 在排队后被停用、删除或移除模型时，Worker 按当前 PostgreSQL 状态拒绝执行，不回退静态配置。

### CHAT-MODEL-005 State boundary

模型列表与输入区选择由 `ModelContext` 管理，不写入 `localStorage`。
模型绑定持久化在已有 Conversation metadata JSON 中；打开或刷新对话时从详情 metadata 恢复选择，
新对话使用输入区当前选择。认证 token 变化时先清空目录与选择，旧账号的迟到响应不得写入新账号 Context。

## 3. Acceptance Criteria

- `/api/models` 返回全局已启用模型及可直接渲染的名称、版本和 icon 标识。
- `/api/models` 在 cache hit 时返回全局 Redis 模型列表，在 miss/损坏时从 PostgreSQL 重建并回填。
- 所有登录用户得到相同模型列表和默认值，响应不含任何连接参数或凭据。
- 输入区能够选择真实模型，且运行期间不可切换。
- 所选模型进入当前 Run 的 Agent context，并由 Worker 使用对应 Provider 连接构造 ChatModel。
- 后端单测和前端 ESLint、TypeScript、生产构建通过。
