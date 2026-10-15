# Model Provider 应用接入

计划版本：v0.4.0

实现状态：已接入代码，等待目标部署环境完成迁移与真实供应商凭据验收。

## 1. 当前任务

仓库已经形成全局 Provider 应用闭环：lifespan 补齐预置并预热模型列表，管理员路由已挂载，
`GET /api/models` 使用 PostgreSQL 投影与 Redis 缓存，Worker 按 Run 模型 ID 解析连接并注入 Agent。
HTTP DTO、Provider 领域模型、ORM 和运行时连接对象已经分层，旧静态 Chat 目录与 `load_model()` 已删除。

本次任务把现有 Provider 内核接入启动、管理、模型列表和 Agent 执行链路，使一次管理员配置能够被
模型选择与后续 Run 使用。具体实施按
[平台配置生命周期](./implementation/platform-lifecycle.md)、
[模型列表与选择](./implementation/model-list.md) 和
[运行时连接](./implementation/runtime-connection.md) 三个能力切片完成。

## 2. 任务目标

1. PostgreSQL 中的全局 Provider 是 Chat 模型配置与连接参数的唯一真相。
2. FastAPI 启动时只补齐缺失预置；管理员保存后立即更新全局模型列表。
3. 登录用户从同一模型列表选择模型，选择值统一使用 `provider/model`。
4. Worker 按 Run 中保存的模型 ID 从 PostgreSQL 解析连接并构造 ChatModel，不再读取静态 Chat Provider。
5. API Key、额外请求头和请求体覆盖只存在于服务端配置与单次运行对象中，不进入 Redis、Run metadata、事件或日志。
6. HTTP 传输 DTO、Provider 领域模型、数据库 ORM 和运行时连接对象各自归属明确，核心 Model 模块不依赖 `server`。

## 3. 如何修改

- 接入 Auth Domain 提供的管理员依赖；Provider 管理、发现和测试路由只接受管理员，普通登录用户只读取模型列表。
- 在 lifespan 的数据库初始化后调用现有 `ensure_builtin_model_providers()`，成功后预热全局模型列表；Redis 失败不阻止启动。
- 由 Model Service 从已启用 Provider 投影公开模型项，使用 `model:chat:list:v3` 做一小时 read-through cache；写事务提交后重建。
- 将组合模型 ID 统一为 `provider/model`，按第一个 `/` 切分；预置的 `provider_id` 与现有 Run 前缀保持一致。
- 将 `server/entities/model.py` 收敛为 Router 使用的请求与响应 DTO；Provider 校验和 Service 写入命令移到
  `src/model/provider.py`，`ModelConnection` 与 `create_chat_model()` 移到 `src/model/runtime.py`。
- Model Service 负责 DTO、Provider 领域对象和 ORM 写入值之间的映射；Repository 只接收 ORM 字段，不依赖 HTTP DTO 或运行时对象。
- 在 Run 创建时用 PostgreSQL 校验模型，在 Worker 执行时重新解析 `ModelConnection`，再由协议工厂创建 LangChain ChatModel。
- Settings 从管理 API 动态读取 Provider，不保留前端固定供应商数组；普通用户不显示 Models 管理入口。
- 将 Leader、SubAgent、摘要和知识抽取等 Chat 调用迁移到显式注入的 ChatModel；确认旧路径无引用后，移除
  `DEFAULT_BASE_MODEL_PROVIER`、静态 Chat 目录投影和 `load_model(model: str)`，保留 Embedding 与 Rerank 配置。

## 4. 实施步骤

1. 完成管理员依赖并接入 Provider 管理路由，接入 lifespan 预置补齐。
2. 实现 PostgreSQL 模型列表投影、严格缓存解码、预热和写后刷新，切换 `GET /api/models`。
3. 将 Settings 改为动态 Provider 列表，并按管理员身份控制入口。
4. 拆分传输、Provider 领域和运行时类型，统一模型 ID，接入 Run 创建校验、Worker 连接解析和
   `create_chat_model()` 协议工厂。
5. 逐个迁移现有 Chat 调用方；确认静态 Chat 目录与 `load_model(model: str)` 无引用后再退役旧路径，完成后端、前端和真实启动链路验证。

## 5. 验收标准

- 首次启动补齐预置，重复启动不覆盖已保存配置；数据库失败阻止启动，Redis 失败不阻止启动。
- 普通用户可读模型列表但不能访问 Provider 管理接口；管理员可以读取、保存、发现和测试 Provider。
- Settings 与 Chat 都不硬编码供应商或模型；Redis 命中、缺失、损坏和不可用时返回同一 PostgreSQL 投影。
- 选中的 `provider/model` 被保存到 Conversation 与 Run，普通 Run、子 Run 和 Resume 均使用对应 PostgreSQL 连接。
- `server/entities/model.py` 不再定义 Provider 写入命令或运行时连接对象，`src/model` 不反向依赖 `server`，Repository 不依赖 DTO。
- 停用或删除 Provider、移除模型和不支持的协议在执行前产生确定性错误，不回退静态配置。
- 外部响应、Redis、日志、Run metadata 和事件均不包含 API Key、额外请求头或完整连接对象。
- Provider、缓存、授权、Run/Worker 和前端交互的定向测试通过；后端 Ruff、前端 typecheck/lint/test/build、`git diff --check` 通过。
