# 全局模型供应商预置与模型目录

计划版本：v0.3.0

## 1. 问题与事实

目标行为以 Yuxi 的平台级 Provider 模型为准：一套 Provider 配置供全部用户共享，`provider_id` 全局唯一，
FastAPI 启动时补齐内置定义并重建模型缓存。变更前仓库实现把 `model_provider` 建模为
`(user_id, provider_id)` 联合主键，并在 Settings Service 与 Redis key 中传播用户范围。

本轮需要把 Provider 从“个人连接配置”恢复为“平台基础设施配置”，同时保留本仓库现有的凭据加密、
出站安全和公开目录脱敏边界。整体 Mermaid 流程见
[Model System Architecture](../../../architecture/model-system.md)。

### 当前实施切片：Provider 内核

用户本次要求先实现 Provider，暂缓应用接入。本切片交付预置字段类、全局 ORM / Repository、
显式补齐 Service、全局配置读写、远程探测和内部连接解析，以及 `0015_model_provider_global` 迁移文件。
预置补齐入口由调用方显式调用，现有 lifespan、认证注册、前端和 Agent 构造继续使用原有路径。

Provider 管理路由保留定义但暂不挂载到 `/api/models`；后续按 3.5 的管理员授权合同接入。
`GET /api/models` 继续返回现有静态 Chat 目录，已有静态 Redis 缓存保持原合同。
本切片的 Provider 写入只提交 PostgreSQL，返回 `cache_refreshed=false`；`list_enabled_models(db)`
直接读取 PostgreSQL。3.4 和 3.6 的 Redis v3 目录及写后刷新由下一接入切片完成。

## 2. 不变量

1. PostgreSQL 只有一套平台 Provider 配置，`provider_id` 是主键，不包含 `user_id`。
2. 代码预置只插入缺失 Provider；重启和预置更新不覆盖管理员已保存的配置。
3. 用户注册、登录和删除不创建、复制、修改或删除 Provider。
4. Provider 管理是管理员行为；所有登录用户只读同一份公开 Chat 模型目录。
5. Redis 只保存全局已启用 Chat 模型的公开目录，可删除、可过期、可从 PostgreSQL 重建。
6. Provider 写入先提交 PostgreSQL，再刷新全局目录；Redis 不成为配置真相。
7. Redis 目录不保存 Base URL、API Key、额外请求头或可用于出站请求的完整连接配置。

## 3. 责任分解

### 3.1 预置声明

在 `src/model/providers/builtin.py` 定义冻结的 `PresetChatModel`、`ModelProviderPreset` 和显式预置 tuple。
模块不依赖 `server.*`、SQLAlchemy、Redis 或环境密钥。初始定义：

| Provider | `provider_id` | Base URL | 初始模型 | 初始启用 |
| --- | --- | --- | --- | --- |
| DeepSeek | `deepseek` | `https://api.deepseek.com/v1` | `deepseek-v4-pro`、`deepseek-v4-flash` | `false` |
| Qwen | `qwen` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen3.6-plus`、`qwen3.5-27b`、`qwen3.6-35b-a3b`、`qwen3.8-max` | `false` |

预置模型包含 `model_id`、`model_type`、`body_overrides` 和 `capabilities`。API Key 与额外请求头为空，
不从环境变量导入。Preset 类只声明字段；启动 Service 显式映射字段、复制 JSON 容器并复用现有 DTO 校验。

预置到 `model_provider` 的映射为：

| 数据库字段 | 来源 |
| --- | --- |
| `provider_id` / `name` / `base_url` / `protocol` / `is_enabled` | `ModelProviderPreset` 同名字段 |
| `enabled_models` | 将 `PresetChatModel` tuple 转为新的 JSON list |
| `api_key` | 空字符串 |
| `extra_headers` | 空字典 |
| `created_at` / `updated_at` | 数据库默认值 |

#### 3.1.1 Preset 类定义

以下是 `src/model/providers/builtin.py` 的目标类内容。`PresetChatModel` 描述单个预置模型，
`ModelProviderPreset` 描述供应商及其初始模型清单；两个类均使用标准库冻结 dataclass，只声明字段和默认值。
`is_enabled` 属于供应商总开关，单个模型是否启用由是否包含在 `enabled_models` 中表达。

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import JsonValue


ModelType = Literal[
    "deepseek", "qwen", "glm", "minomax",
    "gemini", "chatgpt", "ollama", "vllm",
]
ModelProtocol = Literal["openai_compatible"]
ChatCapability = Literal[
    "chat", "vision", "reasoning", "tools", "code", "audio", "video",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class PresetChatModel:
    model_id: str
    model_type: ModelType
    body_overrides: dict[str, JsonValue] = field(default_factory=dict)
    capabilities: tuple[ChatCapability, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelProviderPreset:
    provider_id: str
    name: str
    base_url: str
    enabled_models: tuple[PresetChatModel, ...]
    protocol: ModelProtocol = "openai_compatible"
    is_enabled: bool = False
```

字段重绑定由 `frozen=True` 限制；嵌套 `body_overrides` 按静态配置只读约定使用，Service 映射时做深拷贝。
所有运行时校验都在启动 Service 中显式执行。

#### 3.1.2 Service 字段映射与校验

`server/service/model_service.py` 的启动补齐入口逐项读取 Preset 字段，将普通 dict 交给现有
`ModelProviderCreate.model_validate()`。映射和校验在数据库事务写入前完成，核心逻辑如下：

```python
from copy import deepcopy

from server.entities.model import ModelProviderCreate
from src.model.providers.builtin import MODEL_PROVIDER_PRESETS


pending: list[ModelProviderCreate] = []
seen_provider_ids: set[str] = set()

for preset in MODEL_PROVIDER_PRESETS:
    config = ModelProviderCreate.model_validate({
        "provider_id": preset.provider_id,
        "name": preset.name,
        "base_url": preset.base_url,
        "protocol": preset.protocol,
        "is_enabled": preset.is_enabled,
        "api_key": "",
        "extra_headers": {},
        "enabled_models": [
            {
                "model_id": model.model_id,
                "model_type": model.model_type,
                "body_overrides": deepcopy(model.body_overrides),
                "capabilities": list(model.capabilities),
            }
            for model in preset.enabled_models
        ],
    })
    if config.provider_id in seen_provider_ids:
        raise ValueError("预置供应商 ID 不得重复")
    if not config.enabled_models:
        raise ValueError("预置模型列表不能为空")
    seen_provider_ids.add(config.provider_id)
    pending.append(config)
```

以上是启动 Service 函数内的逻辑示例，执行时机为 lifespan 初始化数据库之后。
`ModelProviderCreate` 和 `EnabledModel` DTO 承担 Provider ID、名称、URL、模型类型、协议、能力、
模型唯一性和请求体覆盖校验；能力数组的重复值校验也归 DTO。预置集合重复和非空清单由 Service 检查。
`server/entities/model.py` 复用 `builtin.py` 的三个 Literal 类型别名，字段校验继续由 DTO 拥有。

Service 全量校验得到 `pending` 后，复用现有 `_write_values(config)` 生成仓储写入值，再交给
Repository 执行 conflict-safe insert；凭据加密由现有 ORM 类型完成。
每次映射都新建模型 dict / list、能力列表和请求头 dict，并深拷贝推理参数，保持 ORM 与预置数据独立。
DNS / IP 安全检查由远程请求边界执行，启动校验只检查 URL 结构。

#### 3.1.3 DeepSeek / Qwen 定义与启动消费

首批预置实例在两个类之后显式构造，省略的 `protocol`、`is_enabled`、`body_overrides` 和 `capabilities`
均采用类默认值。以下 ID 沿用本仓库当前静态配置；这份示例不表示本轮做过厂商 API 联调。

```python
MODEL_PROVIDER_PRESETS: tuple[ModelProviderPreset, ...] = (
    ModelProviderPreset(
        provider_id="deepseek",
        name="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        enabled_models=(
            PresetChatModel(model_id="deepseek-v4-pro", model_type="deepseek"),
            PresetChatModel(model_id="deepseek-v4-flash", model_type="deepseek"),
        ),
    ),
    ModelProviderPreset(
        provider_id="qwen",
        name="Qwen",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        enabled_models=(
            PresetChatModel(model_id="qwen3.6-plus", model_type="qwen"),
            PresetChatModel(model_id="qwen3.5-27b", model_type="qwen"),
            PresetChatModel(model_id="qwen3.6-35b-a3b", model_type="qwen"),
            PresetChatModel(model_id="qwen3.8-max", model_type="qwen"),
        ),
    ),
)
```

FastAPI 启动时由 Service 按 3.1.2 显式映射并校验全部 Preset，随后按 `provider_id` 执行
conflict-safe insert。事务提交和 Redis 预热由 Service / lifespan 按后续章节执行。

### 3.2 全局表与既有数据迁移

目标 ORM 的 `provider_id` 是单列主键，删除 `user_id` 外键。Repository 不再在构造函数或查询方法中接收
user_id，所有查找、更新和删除均以全局 `provider_id` 为边界。表的完整字段、`enabled_models` JSON 子结构、
API 投影和敏感字段边界以 [MODEL-PROVIDER-001](./spec.md#model-provider-001-配置持久化) 为准；实现不得再增加
隐式的用户所有权字段。

新增 `0015_model_provider_global` 迁移，将当前按用户表收敛为全局表：

1. 先读取并验证全部记录，不立即修改表。
2. 每个只有一行的 `provider_id` 直接成为候选全局记录。
3. 同名多行忽略 `user_id`、`created_at`、`updated_at` 后比较业务字段；凭据在内存中解密并规范化后比较，
   不输出到日志。语义完全相同的重复行保留确定性的一行。
4. 同名多行存在任一业务差异时，要求通过 Alembic `-x model_provider_global_sources=<JSON>` 为每个冲突
   `provider_id` 显式指定来源 user ID。映射缺失、存在多余项、用户/记录不存在或凭据无法解密时，
   迁移在删除数据或修改 schema 前停止。
5. 完整验证通过后删除未选行，移除用户外键和联合主键，删除 `user_id` 列，创建 `provider_id` 主键。

执行迁移前必须备份 `model_provider`。降级到按用户表时同样要求通过
`-x model_provider_global_owner=<User.id>` 显式提供一个接收全部全局配置的 owner，
不猜测用户，也不把凭据复制给全部用户。当前切片只交付和测试迁移文件，真实数据库迁移留待部署执行。

### 3.3 FastAPI 启动

Lifespan 在数据库初始化后：

1. 加载并校验全部预置；
2. 对每个 `provider_id` 执行 conflict-safe insert，只补缺失记录；
3. 提交 PostgreSQL；
4. 查询全局已启用 Provider，构建并预热 Redis 公开目录。

预置或数据库步骤失败会中止启动。Redis 预热失败只记录脱敏错误，不阻止 API；`GET /api/models`
随后通过 read-through 自愈。认证注册流程删除 Provider ensure，不再承担模型初始化职责。

### 3.4 全局公开目录

新 key 为 `model:catalog:v3`，替换全局静态 `model:catalog:v2` 与用户级
`model:providers:v2:user:{user_id}`。目录只从 `is_enabled=true` 的 Provider 及其 `enabled_models` 构建，
顶层和模型项结构继续兼容 `GET /api/models`。

模型项只包含 ID、名称、展示名称、版本、provider、icon 与可用性/角色标记；不包含 Base URL、
API Key 原文或密文、额外请求头、请求体覆盖、`has_api_key` 或 ORM 对象。通过完整 DTO 校验缓存内容。

`GET /api/models` 要求登录但不按用户过滤。cache miss、过期、损坏或 Redis 失联时从 PostgreSQL
重建全局目录；Redis 失联时仍返回当次数据库投影。

### 3.5 管理接口与授权

HTTP 路径保持不变：

- `GET /api/models`：登录用户读取全局模型目录。
- `GET /api/models/providers`：管理员从 PostgreSQL 读取全部 Provider 摘要。
- `GET /api/models/providers/{provider_id}`：管理员读取脱敏详情。
- `POST /api/models/providers/{provider_id}`：管理员保存全局配置并刷新目录。
- `/discover`、`/test`：管理员使用表单草稿发起显式远程探测，不落库。

Yuxi 用普通登录依赖保护模型目录、管理员依赖保护 Provider CRUD。本仓库当前没有用户角色或管理员依赖，
因此全局写接口实施前必须先由 Auth Domain 提供可信的管理员授权合同；不能让任意登录用户修改全局凭据。
前端仅为管理员显示 Models 管理入口，普通用户继续使用 Chat 模型选择器。

### 3.6 写后刷新

管理员创建、更新或删除 Provider 时，Service 先提交 PostgreSQL，再删除 `model:catalog:v3`，从已提交数据
重建并以单次 SET 写入完整目录。数据库失败时回滚且不触碰 Redis；Redis 失败时返回
`cache_refreshed=false`，不回滚数据库。

如果 Redis 故障发生在旧 key 删除前，旧目录可能存续至 3600 秒 TTL；Settings 直接读 PostgreSQL，
因此立即显示新配置。Redis 持续不可用时 `/api/models` 直接读 PostgreSQL。

## 4. 一致性与失败处理

| 场景 | PostgreSQL | Redis | 对外行为 |
| --- | --- | --- | --- |
| 预置校验/启动补齐失败 | 回滚或不写 | 不发布 | FastAPI 启动失败 |
| 启动预热失败 | 已提交 | 缺失或遗留旧目录 | API 启动；miss/失联读 SQL，旧 key 由 TTL 淘汰 |
| 非管理员管理请求 | 不写 | 不变 | 返回 403 |
| 管理员保存失败 | 回滚 | 不变 | 返回保存失败 |
| 保存成功、刷新失败 | 已提交 | 已删除，或旧目录保留至 TTL | 返回 `cache_refreshed=false` |
| 目录损坏/过期 | 不变 | 重建 | `/api/models` 返回 SQL 当前投影 |

## 5. 兼容边界

`model:catalog:v3` 不读取、不就地改写旧 v2 key；旧 key 依靠 TTL 清理。全局化迁移只改变 Provider 所有权，
不改变现有字段加密格式。当前 `provider/model` Run metadata 保持不变。

本轮替换 Chat 展示目录的数据来源，但不把 PostgreSQL 中的 Base URL、API Key 或额外请求头接入
Agent 模型构造。目录项的 `is_available` 仍按静态 loader 能否执行同一 ID 计算；尚不能执行的模型可展示但不可选择。

## 6. Yuxi 参考实现取舍

直接采用 Yuxi 的以下结构：全局 `provider_id`、启动一次 ensure、管理员管理 Provider、普通登录用户读取
同一模型目录，以及数据库提交后重建缓存。

本项目保留两项差异：只管理 Chat 模型；Redis v3 是面向前端的公开目录，不像 Yuxi 运行时缓存那样保存
API Key 和完整连接参数。后续若接入运行时连接，应单独设计受控的服务端解析路径，而不是扩大公开缓存字段。

## 7. 验证

- 预置：纯字段类、Service 全量校验、重复 provider/model、映射容器独立、配置不含凭据。
- 迁移：空表、单行、相同重复行、冲突行无映射、合法显式映射、解密失败和 schema 结果。
- Repository/Service：全局 CRUD、重复补齐、已修改行不变、新预置只补缺失行。
- Lifespan：数据库失败中止、Redis 失败不中止、启动只构建一份全局目录。
- Authorization：普通用户可读 `/api/models` 但所有 Provider 管理、发现和测试接口返回 403。
- Cache/API：global hit/miss/损坏/TTL/Redis 失联，目录不含连接参数，所有登录用户得到相同响应。
- Web：管理员看到动态 Provider 管理入口，普通用户不显示入口，Chat 选择器共享同一目录。
- 执行迁移与后端定向测试、前端 typecheck/lint/test/build 和 `git diff --check`。

### Provider 内核切片验证结果

- 54 项模型定向测试和 108 项 subtest 通过，使用临时 SQLite、模拟 Redis 和 HTTP mock。
- 验证预置补齐幂等、全量校验失败时零写入、已有配置和密文保留、全局所有权、用户删除不影响 Provider，
  以及冲突映射、解密失败和显式降级 owner 的迁移行为。
- 验证 Provider 管理路径尚未挂载、现有 Chat 目录仍走静态路径，Provider 写入不发布 Redis 目录。
- 改动代码通过 Ruff，后端 compileall 与 `git diff --check` 通过；Alembic revision 图只有
  `0015_model_provider_global` 一个 head。
- 本切片验证范围为代码、临时测试数据库和迁移图；真实 PostgreSQL 迁移、供应商联调及应用接入在后续执行。
