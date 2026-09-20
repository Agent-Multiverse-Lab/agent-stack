# Model Provider Management

## 1. Scope

提供个人 Chat 模型供应商的 Service / Repository 能力，以及用户范围内的运行时连接参数查询入口。
只接入可用于聊天的单模态和多模态模型，不管理 Embedding、Rerank 或其他非 Chat 模型。
PostgreSQL 是配置的权威来源；配置通过 `user_id` 绑定 `User.id`，只能由所属用户访问。
模块边界遵循 `docs/architecture/overview.md`，存储约束遵循 PS-OWN-001～003。

## 2. Requirements

### MODEL-PROVIDER-001 配置持久化

一张 `model_provider` 表保存一个供应商的配置：

- `user_id`：所属用户外键，与 `provider_id` 构成联合主键；不同用户可保存相同供应商 ID。
- `provider_id`：用户范围内唯一、稳定的业务标识，例如 `siliconflow`、`deepseek`、`ollama`。
- `name`、`base_url`、`protocol`、`api_key`、`extra_headers`、`is_enabled`。
- `enabled_models`：JSON 聊天模型条目列表，每项包含 `model_id`、`model_type`、`body_overrides`，以及可选的 `capabilities` 展示能力列表（默认空）。
- `created_at`、`updated_at`。

供应商 ID 与协议分开建模。首版实现 `openai_compatible` 协议，不能把供应商名称当作协议。
`enabled_models` 只保存聊天模型，同一供应商下 `model_id` 不得重复。
单模态和多模态模型使用同一条管理与连接解析链路，不增加固定为 chat 的 `capability` 字段。
不额外创建模型表或供应商子类。

`model_type` 保留用户指定的类型：`deepseek`、`qwen`、`glm`、`minomax`、`gemini`、
`chatgpt`、`ollama`、`vllm`。其中 `ollama`、`vllm` 保留部署类型标识；按本轮安全要求，
出站连接一律禁止内网地址，这两种类型也必须通过公网 HTTPS 入口接入。
类型记录在模型条目上，因此同一个 `siliconflow` 供应商可配置 `qwen`、`deepseek` 等不同类型。
模型类型与请求协议独立保存；本地部署的 Qwen
模型按所选接入类型记录为 `ollama` 或 `vllm`。不增加可由类型推导的 `is_local` 存储字段。

Repository 只承担供应商的新增、读取、更新和删除及 `flush`；Service 控制提交、回滚和后续缓存刷新。
Repository 构造时必须绑定有效 user_id，读取和写入均不可跨越该用户范围；禁止更新所有者。
更新替换完整模型列表，更新供应商 ID 不受支持。供应商删除后不可解析其模型。

### MODEL-PROVIDER-002 配置校验

- `provider_id` 使用小写字母、数字、下划线或连字符，不包含冒号；`model_id` 非空且无首尾空白。
- 组合 ID 使用 `provider_id:model_id`，以第一个冒号切分，保留模型名称里的 `/` 和后续冒号。
- `base_url` 为绝对 HTTP(S) URL，不包含用户信息、查询参数或 fragment；统一去掉末尾 `/`。
- 拒绝未知模型类型、协议、未知结构字段，以及不能 JSON 序列化的请求体覆盖值。
- `extra_headers` 为字符串映射；拒绝名称或值中的 CR/LF、重复的大小写无关名称以及
  `Host`、`Content-Length`、`Authorization`。API Key 通过独立字段生成认证头。
- `body_overrides` 仅包含供应商聊天推理参数，禁止 `model`、`messages`、`stream` 等运行时
  控制字段，以及 `input`、`query`、`documents` 等其他端点的输入字段；禁止注入
  `api_key`、`base_url`、`headers`。
- 空 API Key 可表示无需认证的本地服务；保存合法不等于远端连接成功。
- 改变 Base URL 时，不允许省略已有 API Key 而自动复用；必须重新提供 Key（空字符串表示清除）。Settings 草稿不携带旧私有请求头到新地址。
- `api_key` 与 `extra_headers` 通过独立的 `MODEL_CREDENTIAL_KEY` 认证加密后落库，ORM 边界解密；缺少密钥或数据无法解密时失败，不回退明文。

### MODEL-PROVIDER-003 远程模型发现

使用保存的连接配置调用 `GET {base_url}/models`，附带配置的认证和额外请求头。
只接收符合 `{ "data": [{ "id": "..." }] }` 结构的有效模型 ID，去重后返回。
发现结果只作为待选择候选，不自动修改 `enabled_models`，也不从模型名称猜测聊天或多模态支持。
供应商明确标记为非 Chat 的条目不作为候选；未提供用途元数据的条目仅表示发现了该 ID，
不宣称已验证可聊天。启用列表由调用方明确选择可用于 Chat 的模型；Settings 凭据测试只验证
当前 Base URL 与 API Key 能否访问供应商模型目录，不替代具体聊天模型的运行验证。
超时、非成功 HTTP 状态及响应结构错误应返回明确且脱敏的失败信息。
出站仅允许 HTTPS 公网目标，检查全部 DNS A/AAAA 结果，拒绝环回、私网、链路本地、共享地址、保留地址和地址转换网段。
连接固定到本次校验的 IP，原域名仅用于 Host 与 TLS SNI；启用正常证书验证，禁用自动重定向和环境代理。
不自动猜测 URL、不跟随重定向，不尝试原生 Ollama `/api/tags` 等其他协议。
用途元数据识别范围为条目的 `type`、`task` 和 `capabilities` 扩展字段；无元数据时不按名称过滤。

### MODEL-PROVIDER-004 连接测试

Settings 使用当前尚未保存的 Base URL 与 API Key 调用后端测试接口；后端携带当前凭据请求
`GET {base_url}/models`，不要求用户先发现或选择具体聊天模型。成功表示供应商接受当前请求并返回
有效模型目录结构；失败返回耗时、脱敏错误类别及可用的上游状态码，401/403 可用于判断当前凭据
不可用。测试不保存草稿、不改变启用状态，也不宣称已验证具体模型的聊天或多模态能力。
使用有界超时；真实供应商探测为显式操作，默认测试套件只使用 HTTP mock。

### MODEL-PROVIDER-005 缓存生命周期

Redis 仅保存用户自己的脱敏启用模型目录，键为 `model:providers:v2:user:{user_id}`，TTL 3600 秒。
所有读取、失效、重建操作显式传入用户 ID，不读取旧的全局缓存键。
缓存不保存 API Key、额外请求头或完整连接参数；缓存不与现有 Chat 展示目录混用。
数据库变更提交成功后先删除旧缓存，再从已提交数据重建并通过单次 SET 替换。
回滚时不发布缓存。缓存 miss 或内容格式无效时从数据库重建。
Redis 故障时目录查询回退数据库；保存结果明确区分数据库已提交与缓存刷新失败。
并发刷新可能短暂留下旧目录，TTL 限定展示陈旧时间；运行时是否可用不依赖这个目录。

### MODEL-PROVIDER-006 运行时连接解析

`resolve_runtime_model(db, user_id, model_ref)` 每次按用户 ID 读取数据库，要求供应商启用且聊天模型已配置。
用户 ID 来自认证用户或可信的运行记录，不允许仅凭 model_ref 解析他人配置。
拒绝未知供应商、停用供应商、不在启用列表中的模型，不回退静态配置。
返回内部类型化连接对象：`provider_id`、`model_id`、`model_type`、`protocol`、`base_url`、
`api_key`、`extra_headers`、`body_overrides`。密钥及额外请求头不参与默认 repr 或日志。
内部对象以 `SecretStr` 保存凭据，通过 `request_headers()` 在请求边界生成完整请求头。
外部列表响应只能返回供应商公开字段和 `has_api_key`，不得直接序列化内部连接对象。

例：`ollama:qwen3:8b` 按 `provider_id=ollama`、`model_id=qwen3:8b` 解析。
例：`siliconflow:org/model-name` 完整保留远程模型 ID `org/model-name`。

## 3. 本次边界

首版交付后端可调用服务、仓储、数据库实体、缓存方法与确定性测试。
现有 Chat 的静态目录、`provider/model` ID 和模型实例构造仍由
`docs/spec/product/chat-model-selection/spec.md` 约束，本轮不迁移该调用链。
Settings 管理页面、登录认证下的管理 HTTP 接口与能力标签展示由
`docs/spec/product/model-settings/spec.md` 的 MODEL-SETTINGS-003～005 定义。
不自动导入环境变量密钥或把现有静态配置写入数据库，不迁移历史 Run/Knowledge 的模型标识。

## 4. Acceptance

- 两个用户的同名供应商各自独立，CRUD、详情、发现、检测、运行时连接及缓存均不得串用。
- HTTP 请求不接收客户端指定的 user_id；服务端仅从 AuthenticatedUser.id 传递所有权。
- 旧全局配置迁移必须明确指定归属；缺少归属映射时迁移停止，保留原数据，不猜测所有者或复制密钥。

- 供应商 CRUD 与停用、单模态/多模态聊天模型配置均可通过 Service 完成并持久化。
- 八种模型类型均能保存并在用户目录和内部解析结果中保留；模型类型不绕过公网 HTTPS 出站限制。
- 非法配置在写库前被拒绝；数据库唯一约束处理重复供应商。
- 远程列表发现和 Settings 凭据测试的成功与失败均有确定性测试；明确非 Chat 的候选被过滤。
- 提交后刷新、回滚不刷新、缓存损坏、Redis 失联均有测试。
- 运行时解析覆盖斜杠和冒号模型名称，以及停用、删除、模型未配置场景。
- 公开输出和错误消息不泄露密钥或额外请求头。
