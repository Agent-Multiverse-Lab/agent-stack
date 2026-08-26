# Specification: Chat Model Selection

## 1. Purpose

在 Chat 输入区提供真实模型选择。模型名称、版本、Provider 和图标标识等展示元数据由
Provider config 生成，并通过 Redis read-through cache 提供。

## 2. Requirements

### CHAT-MODEL-001 Canonical catalog

`DEFAULT_BASE_MODEL_PROVIER` 与系统模型配置是模型目录的权威来源。每个目录项包含：

- `id`：`provider/model`；
- `name`：原始模型名称；
- `display_name`：模型家族缩写，例如 `Qwen`；
- `version`：用于输入区展示的型号版本；
- `provider` 与 `icon`；
- `is_available`：当前 ChatModel loader 是否支持该 Provider；
- 现有的 `is_default / is_fallback / is_flash` 标记。

### CHAT-MODEL-002 Redis read-through cache

`src/model/model_cache.py` 先读取 Redis key `model:catalog:v1`。cache miss 或缓存内容失效时
从 Provider config 重建目录，写入一小时 TTL 后返回；TTL 内请求直接返回缓存。Redis 不可用
时回退 config，且目录不得包含 API Key、base URL 等连接配置。

### CHAT-MODEL-003 Composer selector

`ChatModelSelectComponent` 显示当前模型的 icon、`display_name` 和 `version`，展开后列出
`/api/models` 返回的真实模型。模型目录加载、默认选择和当前选择状态由 `useModelStore`
持有，`ChatView` 只消费 Store；模型目录加载中、无可用模型或
当前 Run 活跃时不允许切换。

### CHAT-MODEL-004 Run integration

提交消息时，选中的模型 ID 写入单次 Run metadata。Worker 重载 Run 后把该值传入
`BaseContext.model`，Leader Agent 使用该模型构造当前 Run 的 ChatModel。后端拒绝不在当前
可用模型目录中的 model ID；目录中暂不可执行的模型只展示且不可选择。

### CHAT-MODEL-005 State boundary

模型选择使用 `useModelStore` 在当前前端会话中共享，不写入 `localStorage`，不持久化为
Conversation 字段，也不修改数据库 schema。页面刷新后重新读取 `/api/models`，并遵循
后端返回的默认模型。

## 3. Non-goals

- 不缓存 LLM 推理响应、Embedding、Rerank 结果或 LangChain 模型对象。
- 不使用数据库保存模型目录。
- 不实现模型目录管理后台或用户自定义模型。

## 4. Acceptance Criteria

- `/api/models` 返回可直接渲染的名称、版本和 icon 标识。
- `/api/models` 在 cache hit 时返回 Redis 目录，在 miss 时从 config 重建并回填。
- 输入区能够选择真实模型，且运行期间不可切换。
- 所选模型进入当前 Run 的 Agent context。
- 后端单测和前端 ESLint、TypeScript、生产构建通过。
