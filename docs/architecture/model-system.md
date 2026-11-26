# Model System Architecture

## 1. Responsibility

Model System 统一管理平台级 Chat / Embedding / Rerank 模型供应商配置、按厂商分组的已启用模型目录缓存、统一模型引用校验与单次运行时模型构造。

- **PostgreSQL（Source of Truth）**：`model_provider` 保存唯一配置真相（启动时按 `src/model/presets.py` 补齐缺失内置供应商模板，不覆盖已有记录；其余供应商由管理员通过管理端/API 创建与维护）；`base_url` 为 Chat 地址，另附 `embedding_base_url`、`rerank_base_url`。
- **Redis**：缓存从 PostgreSQL 派生的全量已启用脱敏模型目录（可按 `category` 过滤；供应商增删改提交后刷新，缓存失效或不可用时回源 PostgreSQL）。
- **协议适配**：
  - Chat（含多模态）使用 LangChain 官方三家整合包（`langchain-openai` / `langchain-anthropic` / `langchain-google-genai`）；
  - Embedding 与 Rerank 直接使用纯 HTTP 请求适配器（不依赖额外厂商 SDK）。

## 2. 目录所有权

`src/model/` 不反向依赖 `server/`，不定义 Pydantic DTO，对外通过 `src/model/__init__.py` 与 `src/model/service.py` 提供统一入口（不提供脱离数据库的纯字符串选型函数）：

- `src/model/presets.py`：内置模型供应商启动预置模板常量；
- `src/model/utils.py`：类型别名（`ModelProtocol`、`ModelCategory`、`ChatCapability`）、参数校验函数、`parse_model_ref` 与 `api_key` 解析（支持环境变量名引用或明文存库）。
- `src/model/repository.py`：`ModelProviderRepository`（操作 `model_provider` ORM 及按 `provider_id:model_id` 查库校验）与 `fetch_model_config`；仅供 `src/model/` 内部使用，业务 Service 不直接访问。
- `src/model/service.py`：启动预置补齐（`ensure_builtin_model_providers`）、供应商 CRUD（`list_model_providers`、`get_model_provider`、`create_model_provider`、`update_model_provider`、`delete_model_provider`）、全量已启用目录构建与 Redis 缓存管理、模型发现与连通性探测，以及面向业务层的单一模型校验入口 `get_enabled_model(db, model_ref, *, category)`。
- `src/model/model_provider/chat.py`、`embedding.py`、`reranker.py`：单次执行实例构造与 `load_chat_model` / `load_embedding_model` / `load_reranker`。

`server/entities/model.py` 定义模型接口 HTTP Schema；`server/router/model_router.py` 提供目录面 `/api/models` 与管理面 `/api/models/providers`（含 CRUD、`/discover`、`/test`），统一通过 `src/model/service.py` 消费，不直接访问 Repository。

## 3. HTTP 接口契约

所有 `/api/models*` 接口统一返回 `{ "status": "success", "data": ... }`，前端 `web/src/api/model.ts` 统一解包 `data`；错误仍由 HTTP 状态码（`404 / 409 / 422 / 500 / 502`）表达。

- **目录面 `GET /api/models?category=chat|embedding|rerank`**（默认 `chat`）：
  `data` 为以 `provider_id` 为键的厂商字典，每项包含 `provider_id`、`display_name`、`models`（元素为 `{ model_id, category, capabilities }`）；仅包含 `is_enabled=true` 且至少有一个匹配 `category` 模型的供应商，不包含 URL / `api_key` / `has_api_key`，不拼接额外 `id`，不计算 `default_model`。无可用模型时 `data` 为 `{}`。
- **管理面 `/api/models/providers`**：
  返回全量供应商配置（含未启用项、三类 URL、协议、`has_api_key` 与完整 `models`），永不回传明文 `api_key`。

## 4. Ownership

| 状态 | Owner | 生命周期 |
| --- | --- | --- |
| Provider 与模型清单 | PostgreSQL `model_provider` | 启动补齐内置模板（不覆盖既有行），管理员维护 |
| 全量已启用模型目录 | PostgreSQL 投影；Redis 是副本 | 1 小时 TTL，供应商变更后刷新，失效可随时重建 |
| Conversation 模型绑定 | PostgreSQL `Conversation.conversation_metadata["model"]` | 对话级显式绑定（可选） |
| Run 模型快照 | PostgreSQL `AgentRun.run_metadata["model"]` | 单次运行冻结快照 |
| Chat / Embedding / Rerank 实例 | 执行内存 | 单次执行构造，不缓存 |

## 5. Runtime Boundary & 选型不变量

模型引用统一为 `provider_id:model_id`，按第一个 `:` 切分（`provider_id` 仅允许 `[a-z0-9_-]`，`model_id` 可继续包含 `/` 或 `:`）。

**显式选型、零 fallback**：不在 `config.py` 中维护 `default_model` / `flash_model` / `fallback_model`，不做跨层级静默降级；任何模型若不存在、供应商已停用或 `category` 不匹配，直接报错。

各业务入口规则：

- **`POST /api/chat/thread`**：`metadata.model` 可选；传入则调 `get_enabled_model(..., category="chat")` 校验并写入绑定，不传则留空。
- **`PATCH /api/chat/thread/{thread_id}`**：修改 `metadata.model` 时查库校验。
- **`POST /api/agent/runs`**：优先使用请求显式传入的 `model`，未传时仅读取当前会话 `conversation_metadata["model"]`；两者皆空或不可用直接报错，有效且与原绑定不同时同步更新会话绑定。
- **排队出队与 Steer**：直接校验当前会话绑定的 `model`，不可用直接报错。
- **Worker 执行**：直接消费 `run_metadata["model"]` 冻结快照，通过 `load_chat_model` 查库构造实例，不重跑选型逻辑。
- **标题生成**：复用当前会话绑定的 `conversation_metadata["model"]`；无绑定或不可用时直接截断首条问题文本，不切换其他模型。
- **SubAgent**：使用子 Agent 自身 `agent_config["model"]`；未单独配置时沿用父 Run 的模型，查库校验不可用直接报错。
- **Embedding / Rerank**：由知识库显式传入或绑定的 `provider_id:model_id`，按对应 `category` 查库校验。

`api_key` 支持环境变量名引用（全大写下划线格式）或明文存库，运行时由 `resolve_provider_api_key` 解析；业务层不接触明文 `api_key`。
