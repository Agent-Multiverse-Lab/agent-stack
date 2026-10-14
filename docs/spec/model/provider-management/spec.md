# Model Provider Management

## 1. Scope

提供平台级 Chat 模型供应商的 Service / Repository 能力，以及全局运行时连接参数查询入口。
只接入可用于聊天的单模态和多模态模型，不管理 Embedding、Rerank 或其他非 Chat 模型。
PostgreSQL 是配置的权威来源；`provider_id` 在平台内唯一，Model Provider 不绑定 User。
系统预置只定义缺失记录的初始值，不是已保存平台配置的平行真相。
模块边界遵循 `docs/architecture/overview.md`，存储约束遵循 PS-OWN-001～003。

## 2. Requirements

### MODEL-PROVIDER-000 系统预置

`src/model/providers/builtin.py` 使用只承载字段的 `ModelProviderPreset` 定义 Chat 供应商初始值。
每项预置包含 `provider_id`、`name`、`base_url`、`protocol`、`is_enabled` 和 `enabled_models`；
模型条目包含 `model_id`、`model_type`、`body_overrides` 和 `capabilities`。预置不包含 API Key、
私有请求头、用户 ID、创建时间或运行对象。
该模块属于 Model Domain，不导入 `server.*`、ORM、Redis 客户端或环境密钥。

`PresetChatModel` 与 `ModelProviderPreset` 的类型合同如下。
稳定的 `ModelType`、`ModelProtocol` 和 `ChatCapability` 类型别名同样由该模块拥有；
`server/entities/model.py` 复用这些定义，不再另建一份允许值集合。

| 类型 | 字段 | Python 类型 | 必填 / 默认值 | 约束 |
| --- | --- | --- | --- | --- |
| `PresetChatModel` | `model_id` | `str` | 必填 | 非空，无首尾空白或控制字符 |
| `PresetChatModel` | `model_type` | `ModelType` | 必填 | 使用 MODEL-PROVIDER-001 的已知类型 |
| `PresetChatModel` | `body_overrides` | `dict[str, JsonValue]` | 默认 `{}`，使用 `default_factory=dict` | 有限 JSON，禁止受保护请求字段；Service 读取时深拷贝 |
| `PresetChatModel` | `capabilities` | `tuple[ChatCapability, ...]` | 默认 `()` | 已知能力且不重复；空 tuple 表示尚无已验证能力元数据 |
| `ModelProviderPreset` | `provider_id` | `str` | 必填 | 长度 1～64，符合 `^[a-z0-9_-]+$`，在预置集合内唯一 |
| `ModelProviderPreset` | `name` | `str` | 必填 | 规范化后的非空展示名称，长度不超过 255 |
| `ModelProviderPreset` | `base_url` | `str` | 必填 | 符合 MODEL-PROVIDER-002 的绝对 URL 约束，去掉末尾 `/` |
| `ModelProviderPreset` | `protocol` | `ModelProtocol` | 默认 `"openai_compatible"` | 当前只允许 `openai_compatible` |
| `ModelProviderPreset` | `is_enabled` | `bool` | 默认 `False` | 供应商总开关，控制其整个模型列表是否进入公开目录；初始由管理员显式启用 |
| `ModelProviderPreset` | `enabled_models` | `tuple[PresetChatModel, ...]` | 必填 | 非空 tuple，`model_id` 在供应商内唯一 |

两个类使用 `@dataclass(frozen=True, slots=True, kw_only=True)`，只声明字段、类型和默认值。
启动 Service 显式读取字段、构建 `ModelProviderCreate` 并完成全部校验；名称 / URL 规范化复用 API DTO。
Service 同时检查预置集合的重复 `provider_id`、非空模型列表和同一供应商内重复模型，全部通过后才执行写库。

完整的目标类定义、Service 字段映射和 DeepSeek / Qwen 构造代码见
[实施计划：Preset 类定义](./plan.md#311-preset-类定义)。

`frozen=True` 保证实例字段不被重新赋值，内嵌 dict / list 仍按静态配置只读约定使用。
Service 为 `body_overrides` 创建深拷贝，并新建模型列表、能力列表和空请求头映射，保持数据库数据与预置容器独立。
`MODEL_PROVIDER_PRESETS` 使用显式 tuple 汇总，不做包扫描或 import-time 数据库写入。

初始清单只纳入仓库中已有完整配置依据的 DeepSeek 和 Qwen。新增供应商时必须同时给出有效
Base URL、协议和真实初始模型清单；不创建占位记录。同一 `provider_id` 只允许一个定义，
所有定义在启动写库前通过与 API DTO 等价的字段校验。
具体初始值为：

| Provider | `provider_id` | Base URL | 初始模型 |
| --- | --- | --- | --- |
| DeepSeek | `deepseek` | `https://api.deepseek.com/v1` | `deepseek-v4-pro`、`deepseek-v4-flash` |
| Qwen | `qwen` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen3.6-plus`、`qwen3.5-27b`、`qwen3.6-35b-a3b`、`qwen3.8-max` |

两项的 `is_enabled=false`、`protocol=openai_compatible`；每个模型的 `model_type` 分别为 `deepseek` 或 `qwen`，
`body_overrides={}`、`capabilities=()`。当前 `model_provider` 没有供应商默认模型字段，
模型角色继续由 Chat 系统配置解析，因此预置不声明 `default_model`，也不创建一份无法落库的平行默认状态。

预置是 bootstrap 数据：缺失的 `provider_id` 按预置插入，已存在记录的全部字段保持不变。
修改预置不会覆盖平台的 Base URL、启用状态、模型选择或凭据；从预置中移除供应商也不删除数据库记录。

FastAPI lifespan 在数据库初始化后补齐一次全局预置。插入依赖 `provider_id` 主键处理多 API 进程并发；
重复启动不产生重复记录，用户注册、登录或删除不触发 Provider 补齐。
预置无效或数据库补齐失败时 FastAPI 启动失败；数据库提交后的 Redis 预热失败不阻止启动。

### MODEL-PROVIDER-001 配置持久化

一张 `model_provider` 表保存一个平台级供应商。目标字段合同如下：

| 字段 | ORM / 数据库类型 | Null / 默认值 | 约束与语义 | 对外可见性 |
| --- | --- | --- | --- | --- |
| `provider_id` | `String(64)` | `NOT NULL` | 单列主键；稳定业务 ID；创建后不可修改；符合 `^[a-z0-9_-]+$`，例如 `deepseek` | 摘要、详情、写入结果可见 |
| `name` | `String(255)` | `NOT NULL` | 去除首尾空白后的非空展示名；不要求全局唯一 | 摘要和详情可见 |
| `base_url` | `Text` | `NOT NULL` | 规范化后的供应商 API 根地址；满足 MODEL-PROVIDER-002 的 URL 和出站安全约束 | 仅管理员详情可见，不进入公开目录 |
| `protocol` | `String(32)` | `NOT NULL` | 请求协议；首版固定为 `openai_compatible`，不等同于供应商名称 | 仅管理员详情可见 |
| `api_key` | `EncryptedCredential`，物理列为 `Text` | `NOT NULL`，默认 `""` | 独立认证凭据；允许空字符串；通过 `MODEL_CREDENTIAL_KEY` 加密落库 | 永不返回，只投影 `has_api_key` |
| `extra_headers` | `EncryptedHeaders`，物理列为 `JSON` | `NOT NULL`，默认 `{}` | 额外请求头字符串映射；整体加密落库；不允许覆盖认证和传输控制头 | 永不返回，也不进入 Redis |
| `is_enabled` | `Boolean` | `NOT NULL`，默认 `false` | 平台总开关；只有启用供应商的模型进入公开目录和运行时解析 | 摘要和详情可见 |
| `enabled_models` | `JSON` | `NOT NULL`，默认 `[]` | 完整替换的 Chat 模型条目数组；结构见下表；同一供应商内 `model_id` 唯一 | 管理员详情返回；公开目录仅返回脱敏投影 |
| `created_at` | `DateTime(timezone=True)` | `NOT NULL`，数据库 `now()` | 首次创建时间；Service 不接受客户端传值 | 不在当前 API 响应中返回 |
| `updated_at` | `DateTime(timezone=True)` | `NOT NULL`，数据库 `now()` | 最近数据库更新时间，更新时由 ORM / 数据库维护 | 不在当前 API 响应中返回 |

表中不包含 `user_id`、`owner_id` 或任何用户外键。`provider_id` 是唯一主键，因此所有用户共享同一条
DeepSeek、Qwen 等供应商记录。`has_api_key` 是读取时根据 `api_key != ""` 计算的响应字段，不落库；
`is_builtin` 可由 `provider_id` 是否存在于代码预置集合推导，也不重复存储。

`enabled_models` 每个 JSON 元素必须严格符合以下结构，不接受未声明字段：

| 字段 | JSON 类型 | 必填 / 默认值 | 约束与语义 |
| --- | --- | --- | --- |
| `model_id` | `string` | 必填 | 供应商侧真实模型 ID；非空，不含首尾空白或控制字符；在当前 Provider 内唯一 |
| `model_type` | `string` | 必填 | `deepseek`、`qwen`、`glm`、`minomax`、`gemini`、`chatgpt`、`ollama`、`vllm` 之一 |
| `body_overrides` | `object` | 默认 `{}` | 有限 JSON 推理参数；不得包含 MODEL-PROVIDER-002 所列运行时和连接受保护字段 |
| `capabilities` | `string[]` | 默认 `[]` | 已验证的展示能力；元素只能是 `chat`、`vision`、`reasoning`、`tools`、`code`、`audio`、`video`，且不得重复 |

数据库中的完整示例为：

```json
{
  "provider_id": "deepseek",
  "name": "DeepSeek",
  "base_url": "https://api.deepseek.com/v1",
  "protocol": "openai_compatible",
  "api_key": "<encrypted-at-rest>",
  "extra_headers": {},
  "is_enabled": true,
  "enabled_models": [
    {
      "model_id": "deepseek-v4-pro",
      "model_type": "deepseek",
      "body_overrides": {},
      "capabilities": ["chat", "reasoning"]
    }
  ],
  "created_at": "<database timestamp>",
  "updated_at": "<database timestamp>"
}
```

API 不直接序列化 ORM。管理员接口使用下列明确投影：

| DTO | 字段 |
| --- | --- |
| `ModelProviderCreate`（Service） | `provider_id`、`name`、`base_url`、`protocol`、`api_key`、`extra_headers`、`is_enabled`、`enabled_models` |
| `ModelProviderUpdate`（Service） | 除不可修改的 `provider_id` 外，与 Create 相同；`api_key` 可省略 |
| `ModelProviderSummary` | `provider_id`、`name`、`is_enabled`、`has_api_key` |
| `ModelProviderResponse` | Summary 全部字段，加 `base_url`、`protocol`、`enabled_models` |
| `ModelSettingsRequest`（Web） | `base_url`、可省略的 `api_key`、`is_enabled`、`models`；`provider_id` 来自 path，`name`、`protocol` 和私有请求头沿用数据库或预置值 |
| `ProviderWriteResult` | `provider_id`、`cache_refreshed` |

`ModelSettingsRequest.models[]` 只接受 `model_id` 和 `capabilities`。Service 将其合并为完整的
`enabled_models[]`：已有模型保留 `model_type` 和合法 `body_overrides`，新发现模型使用当前 Provider 的
已保存配置的唯一模型类型、预置的唯一模型类型或供应商元数据合同确定 `model_type`；
混合类型供应商新增模型时必须通过完整配置显式指定类型，不能由模型名称猜测。Base URL 未改变时，
省略 `api_key` 表示保留旧值；Base URL 改变时省略 Key 会被拒绝；显式空字符串表示清除。

供应商 ID 与协议分开建模。首版实现 `openai_compatible` 协议，不能把供应商名称当作协议。
`enabled_models` 只保存聊天模型，同一供应商下 `model_id` 不得重复。
单模态和多模态模型使用同一条管理与连接解析链路，不增加固定为 chat 的 `capability` 字段。
不额外创建模型表或供应商子类。

`model_type` 保留管理员指定的类型：`deepseek`、`qwen`、`glm`、`minomax`、`gemini`、
`chatgpt`、`ollama`、`vllm`。其中 `ollama`、`vllm` 保留部署类型标识；按本轮安全要求，
出站连接一律禁止内网地址，这两种类型也必须通过公网 HTTPS 入口接入。
类型记录在模型条目上，因此同一个 `siliconflow` 供应商可配置 `qwen`、`deepseek` 等不同类型。
模型类型与请求协议独立保存；本地部署的 Qwen
模型按所选接入类型记录为 `ollama` 或 `vllm`。不增加可由类型推导的 `is_local` 存储字段。

Repository 只承担供应商的新增、读取、更新和删除及 `flush`；Service 控制提交、回滚和后续缓存刷新。
Repository 以 `provider_id` 查询全局记录，不接收 user_id。更新替换完整模型列表，更新供应商 ID 不受支持；
供应商删除后不可解析其模型。`GET /api/models` 对登录用户开放，Provider 列表、详情、写入、发现和测试
均要求管理员权限；不得把普通 `AuthenticatedUser` 直接视为管理员。

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

Settings 使用管理员当前尚未保存的 Base URL 与 API Key 调用后端测试接口；后端携带当前凭据请求
`GET {base_url}/models`，不要求管理员先发现或选择具体聊天模型。成功表示供应商接受当前请求并返回
有效模型目录结构；失败返回耗时、脱敏错误类别及可用的上游状态码，401/403 可用于判断当前凭据
不可用。测试不保存草稿、不改变启用状态，也不宣称已验证具体模型的聊天或多模态能力。
使用有界超时；真实供应商探测为显式操作，默认测试套件只使用 HTTP mock。

### MODEL-PROVIDER-005 缓存生命周期

Redis 保存平台唯一的脱敏、已启用 Chat 模型目录，键为 `model:catalog:v3`，TTL 3600 秒。
目录只从 `is_enabled=true` 的供应商和其 `enabled_models` 构建，每个选择项包含 `id`、`name`、
`display_name`、`version`、`provider`、`icon`、`is_available`、`is_default`、`is_fallback` 和 `is_flash`。
目录不保存 Base URL、API Key 原文或密文、额外请求头、`body_overrides`、`has_api_key` 或 ORM 对象。

`GET /api/models` 只要求用户已登录，所有用户读取同一全局目录。Settings 的供应商列表和详情仍从 PostgreSQL 读取，
不把 Redis 目录当作可编辑配置。缓存 miss、过期或结构校验失败时从 PostgreSQL 重建，
并用单次 SET 写入完整 JSON 目录。Redis 故障时在当次请求中直接返回 PostgreSQL 构建结果。

启动补齐提交后预热一次全局目录。管理员变更供应商并提交成功后先删除旧目录，再从已提交数据重建；
用户注册不触碰目录，数据库事务回滚时不发布缓存。
保存结果明确区分数据库已提交与目录刷新失败。缓存不参与凭据解析或出站请求；
运行时连接参数始终从 PostgreSQL 读取。

### MODEL-PROVIDER-006 运行时连接解析

`resolve_runtime_model(db, model_ref)` 按全局 `provider_id` 读取数据库，要求供应商启用且聊天模型已配置。
拒绝未知供应商、停用供应商、不在启用列表中的模型，不回退静态配置。
返回内部类型化连接对象：`provider_id`、`model_id`、`model_type`、`protocol`、`base_url`、
`api_key`、`extra_headers`、`body_overrides`。密钥及额外请求头不参与默认 repr 或日志。
内部对象以 `SecretStr` 保存凭据，通过 `request_headers()` 在请求边界生成完整请求头。
外部列表响应只能返回供应商公开字段和 `has_api_key`，不得直接序列化内部连接对象。

例：`ollama:qwen3:8b` 按 `provider_id=ollama`、`model_id=qwen3:8b` 解析。
例：`siliconflow:org/model-name` 完整保留远程模型 ID `org/model-name`。

## 3. 本次边界

本轮交付全局预置声明、FastAPI 启动补齐、全局已启用模型目录、管理员 Settings 动态供应商列表和
Chat 输入区动态展示。`provider/model` ID 和模型实例构造仍由
`docs/spec/product/chat-model-selection/spec.md` 约束，本轮不将 Provider 连接参数接入 Agent 模型构造，
不迁移历史 Run/Knowledge 的模型标识。
本轮不从环境变量导入 API Key，也不将凭据写入预置或 Redis。

## 4. Acceptance

- 供应商 CRUD 与停用、单模态/多模态聊天模型配置均可通过 Service 完成并持久化。
- 首次启动全局补齐一份 DeepSeek 和 Qwen；重复启动不增加重复记录，不覆盖已修改配置。
- 用户注册、登录和删除不创建、复制、修改或删除 Provider。
- 启动预热、cache hit、cache miss、缓存损坏和 Redis 失联都返回与 PostgreSQL 等价的全局已启用模型目录。
- Settings 供应商列表不由前端硬编码，仅渲染全局 PostgreSQL 记录；普通用户无管理入口或管理 API 权限。
- `/api/models` 对登录用户返回相同的全局已启用模型，响应不含任何连接配置或凭据。
- 从现有按用户表迁移为全局表时，语义相同的重复行可以合并；存在差异的同名 Provider 必须显式指定保留来源，未指定时迁移在修改数据前停止。
- 八种模型类型均能保存并在全局目录和内部解析结果中保留；模型类型不绕过公网 HTTPS 出站限制。
- 非法配置在写库前被拒绝；数据库唯一约束处理重复供应商。
- 远程列表发现和 Settings 凭据测试的成功与失败均有确定性测试；明确非 Chat 的候选被过滤。
- 提交后刷新、回滚不刷新、缓存损坏、Redis 失联均有测试。
- 运行时解析覆盖斜杠和冒号模型名称，以及停用、删除、模型未配置场景。
- 公开输出和错误消息不泄露密钥或额外请求头。
