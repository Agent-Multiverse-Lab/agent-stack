# Model System Architecture

## 1. Responsibility

Model System 统一管理平台级 Chat / Embedding / Rerank 模型配置、公开模型目录与单次运行时模型构造。
PostgreSQL 保存供应商与模型配置真相（`base_url` 为 Chat 地址，另附 `embedding_base_url`、`rerank_base_url`），Redis 缓存脱敏 Chat 模型列表，`src/model/` 内聚仓储、服务与运行时构造：
- Chat（含多模态）使用 LangChain 官方三家整合包（`langchain-openai` / `langchain-anthropic` / `langchain-google-genai`）；
- Embedding 与 Rerank 直接使用 HTTP URL 请求适配器（不依赖额外厂商 SDK）。

## 2. 目录所有权

`src/model/` 不反向依赖 `server/`，不定义 Pydantic DTO，对外由 `src/model/runtime.py` 与 `src/model/service.py` 提供统一入口；协议构造器与供应商适配器集中在 `src/model/model_provider/`：

- `src/model/utils.py`：类型别名（`ModelType`、`ModelProtocol`、`ModelCategory`、`ChatCapability`）、参数校验函数与 API Key 解析；
- `src/model/presets.py`：内置预置常量（`deepseek`、`dashscope`、`openai`、`anthropic`、`gemini`，按官方默认 `base_url` / `embedding_base_url` / `rerank_base_url` 收录 Chat / Embedding / Rerank）；
- `src/model/repository.py`：`ModelProviderRepository`，仅操作 `model_provider` ORM；
- `src/model/model_provider/chat.py`：纯 ChatModel 协议构造器（`openai_compatible` → `ChatOpenAI`、`anthropic` → `ChatAnthropic`、`gemini` → `ChatGoogleGenerativeAI`）；
- `src/model/model_provider/embedding.py`：纯 HTTP `HttpEmbeddings`（OpenAI 兼容 & Gemini）；
- `src/model/model_provider/reranker.py`：`BaseReranker` 与纯 HTTP `HttpReranker`；
- `src/model/runtime.py`：统一运行时门面（`validate_model`、`load_chat_model`、`load_embedding_model`、`load_reranker`），屏蔽数据库与凭据；
- `src/model/service.py`：预置补齐、Provider CRUD、Redis 目录缓存、模型发现与连通性探测。

`server/entities/model.py` 定义唯一的 HTTP Schema `ModelProvider`（`api_key` 只写不回传），Router 通过 `src/model/service.py` 消费模型管理能力。

## 3. Ownership

| 状态 | Owner | 生命周期 |
| --- | --- | --- |
| Provider 与模型清单 | PostgreSQL `model_provider` | 管理员写入，平台共享 |
| 公开 Chat 模型列表 | PostgreSQL 投影；Redis 是副本 | 一小时 TTL，可随时重建 |
| Conversation 模型绑定 | PostgreSQL Conversation metadata | 对话级选择 |
| Run 模型快照 | PostgreSQL AgentRun metadata | 单次运行选择 |
| 内部解析态 `_ResolvedModel` | `src/model/runtime.py` 内存 | 单次解析瞬态，不对外暴露 |
| Chat / Embedding / Rerank 实例 | 执行内存 | 单次执行构造，不缓存 |

## 4. Runtime Boundary

公开模型 ID 统一为 `provider/model`，按第一个 `/` 切分，模型名称可以继续包含 `/` 或 `:`。
`category`（`chat | embedding | rerank`）用于防混用校验、过滤公开聊天目录及分派测试探测方式；对应类型分别使用 `base_url`、`embedding_base_url`、`rerank_base_url`。
预置供应商默认将 `api_key` 设为环境变量名（如 `DEEPSEEK_API_KEY` / `DASHSCOPE_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY`），解析时读取环境变量或配置默认值，否则按明文返回；HTTP 接口永不回传 `api_key`。
Agent 与业务服务只通过 `validate_model` 校验或 `load_*` 加载实例，不在业务层接触明文 API Key。
