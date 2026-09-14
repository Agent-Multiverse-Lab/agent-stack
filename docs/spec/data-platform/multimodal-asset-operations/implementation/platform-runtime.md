# Platform Runtime Slice

关联需求：DP-MAO-001、DP-MAO-002、DP-MAO-003、DP-MAO-004、DP-MAO-005、DP-MAO-007、
DP-MAO-008、DP-MAO-009  
关联任务：MAO-001、MAO-002

## 1. Files

- `data_platform_server/go.mod`
- `data_platform_server/go.sum`
- `data_platform_server/cmd/server/main.go`
- `data_platform_server/internal/httpapi/handler.go`
- `data_platform_server/internal/platform/model.go`
- `data_platform_server/internal/platform/service.go`
- `data_platform_server/internal/platform/store.go`
- `data_platform_server/internal/platform/operations.go`
- `migrate/versions/<revision>_add_data_platform_tables.py`
- `docker/data-platform.Dockerfile`
- `docker/docker-compose.yml`

`store.go` 直接提供 PostgreSQL 实现；第一版不定义只有单一实现的 repository interface。
`operations.go` 使用代码内固定 map 注册两个 operation，不建立插件加载器。

## 2. Persistence

新增最小表集合：`data_sources`、`data_datasets`、`data_assets`、`data_processing_jobs`、
`data_job_inputs` 和 `data_artifacts`。质量摘要和扩展 metadata 使用受大小限制的 JSONB；血缘由
`data_job_inputs -> data_processing_jobs -> data_artifacts` 表达，不新增独立图数据库或 lineage 表。

`data_processing_jobs.request_id` 建立唯一约束。任务状态更新使用带当前状态条件的 SQL，避免并发执行
覆盖终态。对象引用保存 bucket/key，不保存预签名 URL。

## 3. HTTP handlers

`handler.go` 提供 spec 中六个端点，统一返回：

```json
{
  "data": {},
  "error": null,
  "request_id": "request-id"
}
```

错误使用稳定 code：`invalid_request`、`forbidden`、`not_found`、`conflict`、
`operation_failed`、`temporarily_unavailable`。handler 只做解码、可信调用上下文提取和响应映射，
边界检查与状态变更由 `platform.Service` 完成。

## 4. Execution

`CreateJob` 在事务中验证 operation、输入权限、类型和幂等键并提交 `queued`。Go 服务内的固定
worker 通过 PostgreSQL `FOR UPDATE SKIP LOCKED` 原子认领任务并进入 `running`，执行 operation，
写入 MinIO 成果，再以一个数据库事务写成果并进入 `succeeded`。

第一版不实现 Redis 平台队列、分布式 Worker 服务、优先级队列或自动重试。进程重启后继续认领
`queued` 任务，并把超过租约时间的 `running` 任务恢复为可认领状态；operation 必须以 job ID
派生固定输出 key，使重复执行覆盖同一未发布对象而不是生成多个成果。

## 5. Operation examples

目标文件：`data_platform_server/internal/platform/operations.go`。

- `normalize_asset`：读取受限大小的 JSON、CSV 或测试图片；验证 content type 与 checksum；输出规范化
  metadata JSON 和原内容引用摘要。
- `compare_asset_versions`：只接受同一 dataset 的两个资产；比较 checksum、规范化 metadata 和受限的
  文本/表格内容；输出 JSON diff。图片第一版只比较文件与 metadata，不实现像素级模型。

## 6. Tests

- handler 解码与错误 code
- 无界检索拒绝、分页上限和项目隔离
- request ID 并发重复提交
- 状态迁移与幂等取消
- 对象写入、成果事务和失败补偿
- 重启恢复不产生重复成果
