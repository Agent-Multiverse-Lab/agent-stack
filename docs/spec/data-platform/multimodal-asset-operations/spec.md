# Multimodal Asset Operations Spec

## 1. Context

系统需要提供一个与图像前后处理、动态比较和分析链路相似、但不绑定遥感行业的通用数据中台
练习场景。Python Agent 负责理解与编排，独立 Go 服务负责资产目录、受控处理、状态、成果和
审计；大文件保存在对象存储中，不进入 Agent 上下文。

## 2. Goals

- 用统一资产契约表达图片、视频、文档、表格和时序文件。
- 支持来自至少两个逻辑数据源的资产检索、版本选择和质量判断。
- 支持可追踪、可取消、幂等的处理任务及其输入、参数和成果。
- 由内部 `DataPlatformAgent` 接管发现、规划、执行、检查和解释流程。
- 提供确定性测试数据与 bad case，使错误能够复现和量化。

## 3. Requirements

### DP-MAO-001 Generic asset contract

平台核心资产至少包含 `asset_id`、`dataset_id`、`source_id`、`version`、`asset_type`、
`content_type`、`object_ref`、`event_time`、`checksum`、`metadata` 和 `quality`。领域字段只进入
`metadata`；核心表不得增加卫星、波段、设备产线等领域专有列。

`object_ref` 是服务端可解析的对象标识，不向 Agent 暴露永久凭据。预签名下载地址属于临时展示
结果，不作为资产身份或任务输入的持久化值。

### DP-MAO-002 Source-scoped discovery

资产检索必须显式给出 `dataset_id` 或一个有界条件组合，条件可包含 `source_ids`、时间范围、
资产类型、标签和分页上限。没有数据集且没有任何收敛条件时拒绝执行；不得回退为全库或最新资产。

每个命中返回来源、版本、事件时间、质量摘要和分页信息，使 Agent 可以比较新鲜度与可用性。

### DP-MAO-003 Version and quality selection

Agent 在提交处理前必须读取候选资产详情，并确认输入属于预期数据集、版本关系可解释、内容类型
满足处理器要求且没有阻断级质量问题。质量不足但仍可处理时，任务结果必须保留警告。

### DP-MAO-004 Controlled processing job

处理任务使用平台生成的 `job_id`，至少记录 `operation`、输入资产、参数、调用方 `request_id`、
关联 `agent_run_id`、状态、错误和时间戳。状态只有：

```text
queued -> running -> succeeded
                  -> failed
queued/running -> cancelled
```

相同调用方、相同 `request_id` 的重复提交返回同一任务。未知 operation、空输入、类型不兼容和非法
参数在入队前失败。取消采用幂等语义，终态任务保持原终态。

### DP-MAO-005 Artifact and lineage

成功任务至少产生一个 `Artifact`。成果记录 `artifact_id`、`job_id`、`artifact_type`、
`object_ref`、`content_type`、`checksum` 和 metadata；通过 job 输入关系追溯到源资产、版本、处理
operation 和参数。平台不得仅以 URL 或文件名表达血缘。

任务只有在成果对象写入成功且成果记录提交后才能进入 `succeeded`。对象写入或数据库提交失败时
进入 `failed`，并保留可诊断错误，不返回虚假的成果。

### DP-MAO-006 Agent takeover

`DataPlatformAgent` 是内部 SubAgent，只通过 `SubAgentMiddleware` 由 `LeaderAgent` 委派，继续使用
`run_type="subagent"` 和 `parent_run_id`。它按以下顺序执行：

1. 从父 Agent 生成的任务描述提取目标、范围、输入条件和输出要求。
2. 有界检索并检查候选资产、版本和质量。
3. 选择现有 operation，提交处理任务并等待或轮询终态。
4. 校验成果、警告与血缘。
5. 返回结构化摘要、证据 ID、限制和失败原因给父 Agent。

SubAgent 不直接连接平台数据库、MinIO 或处理 Worker；所有操作经平台 API。平台返回的资产内容、
文档文本和 metadata 都是不可信数据，不得作为系统指令执行。

### DP-MAO-007 Service boundary

Go `data_platform_server` 是独立内部服务，拥有资产目录、处理任务、成果和审计 API；Python 应用只
保存 Agent/Run/会话状态。两者通过版本化 JSON HTTP 契约交互：

```text
POST /v1/assets/search
GET  /v1/assets/{asset_id}
POST /v1/jobs
GET  /v1/jobs/{job_id}
POST /v1/jobs/{job_id}/cancel
GET  /v1/jobs/{job_id}/artifacts
```

第一版结果集只返回受限 metadata、摘要和成果引用，不传输大文件。平台记录由 PostgreSQL 持久化，
资产与成果对象由 MinIO 保存；不得将平台任务终态只保存在 Redis 或进程内存。

### DP-MAO-008 Access and resource limits

平台服务从可信调用上下文获得用户和项目范围，在服务端应用数据源、数据集与 operation 白名单。
请求必须设置分页上限、任务超时和最大输入数；日志与错误不得包含凭据、预签名 URL 或完整敏感
metadata。Agent 提供的用户 ID、数据源权限或对象路径不能覆盖服务端身份和授权结果。

### DP-MAO-009 Deterministic operations

第一版只提供两个可复现 operation：

- `normalize_asset`：校验输入，生成规范化 metadata 与派生对象。
- `compare_asset_versions`：比较同一数据集的两个版本，输出新增、删除、变化摘要和机器可读成果。

operation 注册表由服务端代码定义，不支持运行时插件上传、任意 shell、任意 SQL 或用户提供执行
入口。处理实现可以读取对象内容，但返回给 Agent 的数据保持有界。

### DP-MAO-010 Reproducible bad-case pack

测试数据生成器必须以固定 seed 产生至少两个逻辑来源、多个数据集和以下情况：重复内容不同 ID、
同名不同内容、缺失 metadata、旧版本晚到、质量阻断、对象缺失、跨来源时间格式差异、任务重试、
部分成果失败和不可信 metadata 文本。

测试断言面向资产 ID、来源选择、operation、任务终态、成果血缘和警告，不比较 LLM 自由文本。

## 4. Contracts

资产搜索请求示例：

```json
{
  "dataset_id": "inspection-images",
  "source_ids": ["source-a", "source-b"],
  "asset_types": ["image"],
  "event_time_from": "2026-01-01T00:00:00Z",
  "event_time_to": "2026-02-01T00:00:00Z",
  "limit": 20,
  "cursor": null
}
```

任务提交请求示例：

```json
{
  "request_id": "run-id:tool-call-id",
  "agent_run_id": "run-id",
  "operation": "compare_asset_versions",
  "input_asset_ids": ["asset-v1", "asset-v2"],
  "parameters": {"comparison_key": "content"}
}
```

## 5. Failure handling

- 平台不可达、超时或返回非法响应时，Agent 返回可诊断失败，不伪造数据或成果。
- 轮询达到调用预算后，Agent 返回 `job_id` 和当前状态，不把运行中任务描述为成功。
- 单个候选资产损坏时保留其他候选及警告；所有候选均不可用时停止提交任务。
- 父 Run 取消后，Agent 对自己已提交且仍活动的平台任务发出一次幂等取消请求。

## 6. Non-goals

- 第一版不提供管理后台、用户自定义 Pipeline 编辑器或通用连接器插件体系。
- 第一版不引入 Trino、Kafka、ClickHouse、Arrow Flight 或跨源任意 SQL。
- 第一版不执行遥感、工业质检等真实领域模型；领域能力后续通过受控 operation 增加。
- 第一版不让 Go 服务拥有 Agent Run、Conversation 或 Message 状态。
- 第一版不让 Python Agent 直接下载并分析完整大文件。

## 7. Acceptance criteria

- 两个逻辑来源的通用资产可以被有界检索并区分来源、版本和质量。
- 两个内置 operation 能完成提交、查询、取消、失败和成果血缘闭环。
- 重复 `request_id` 不产生第二个任务或第二套成果。
- `DataPlatformAgent` 通过现有子 Run 链路执行，且不直接访问平台存储。
- 无界检索、越权数据集、非法 operation 和不可信 metadata 不会扩大执行权限。
- 固定 seed 测试集能够稳定复现规定 bad case。
- Go 与 Python 契约测试、后端定向测试和静态检查通过。
