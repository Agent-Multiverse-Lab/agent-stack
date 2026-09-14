# Implementation Plan: Multimodal Asset Operations

计划版本：v0.1.0

## 1. Scope

实现 DP-MAO-001 至 DP-MAO-010 的最小端到端链路：Go 平台服务保存通用资产及处理任务，Python
内部 SubAgent 通过平台 API 完成发现、处理与成果核验，固定 seed 数据包覆盖多源与 bad case。

本计划不修改现有 `SearchAgent`，不新增前端管理页面，不引入通用插件层或联邦 SQL。

## 2. Implementation order

1. 按 [platform-runtime.md](implementation/platform-runtime.md) 建立平台 API、持久化、对象存储和两个
   内置 operation。
2. 按 [agent-runtime.md](implementation/agent-runtime.md) 建立客户端、`DataPlatformAgent` 和父 Agent
   注册。
3. 按 [evaluation-fixtures.md](implementation/evaluation-fixtures.md) 建立固定 seed 数据与跨语言契约
   验证。
4. 端到端验证成功后，新增 `docs/architecture/data-platform-system.md`，更新
   `docs/architecture/README.md`、`overview.md`、`agent-system.md`、`persistence-system.md` 和
   `AGENTS.md` 的阅读路由，只记录已经落地的最终所有权。

每一步完成后仓库保持可启动、可测试；后一切片不得通过伪造上一切片响应绕过真实契约测试。

## 3. Shared constraints

- Agent Run 与平台 Job 是两个状态机：前者由现有 Python/PostgreSQL Run Domain 拥有，后者由 Go
  平台服务拥有；通过 `agent_run_id` 关联，不互相冒充终态。
- 平台数据库表使用现有 Alembic revision 管理，避免引入第二套迁移工具；Go 服务只消费已迁移
  schema。
- MinIO 保存对象，PostgreSQL 保存资产、任务、成果和血缘真相；第一版平台任务不增加 Redis 队列。
- Python 与 Go 共享 HTTP JSON 示例作为契约夹具，不复制一套手工维护的领域模型包。
- 测试 fixture 使用小文件和固定 seed；不向仓库提交大型二进制样本。

## 4. Control-flow example

目标文件：`src/agents/subagents/dataplatformagent/tools.py`，负责函数：`process_assets`。

```python
hits = await client.search_assets(search_request)
selected = [hit for hit in hits.items if not hit.quality.blocked]
if not selected:
    return {"status": "blocked", "warnings": hits.warnings}

job = await client.create_job(
    request_id=f"{run_id}:{tool_call_id}",
    agent_run_id=run_id,
    operation=operation,
    input_asset_ids=[asset.asset_id for asset in selected],
    parameters=parameters,
)
return await client.wait_for_job(job.job_id)
```

目标文件：`data_platform_server/internal/platform/service.go`，负责方法：`CreateJob`。

```go
func (s *Service) CreateJob(ctx context.Context, command CreateJobCommand) (Job, error) {
    if existing, ok := s.store.FindJobByRequestID(ctx, command.RequestID); ok {
        return existing, nil
    }
    operation, ok := s.operations[command.Operation]
    if !ok {
        return Job{}, ErrUnknownOperation
    }
    return s.enqueueValidatedJob(ctx, operation, command)
}
```

实际实现必须在同一事务或唯一约束下完成幂等判断，示例只表达所有权和控制流。

## 5. Failure and rollback

- migration、Go API 或 Python 契约测试未通过时停止当前切片，不注册 `DataPlatformAgent`。
- PostgreSQL 任务认领失败时保留 `queued` 供后续重试；进入 `running` 后的执行失败必须落为
  `failed` 并保存错误。
- 对象已写入但成果事务失败时清理该次未引用对象；清理失败进入可观测日志，不把任务置为成功。
- Agent 注册后若端到端检查失败，修复当前实现；不添加旧新双路径或静默回退到直接存储访问。

## 6. Validation

- `go test ./...`（`data_platform_server/`）
- Python 客户端和 SubAgent 定向 pytest/unittest
- Alembic upgrade/downgrade 针对新增 revision 的临时库验证
- 固定 seed fixture 重建与 checksum 验证
- API 契约、幂等、取消、失败和越权测试
- `ruff check`、`python -m compileall`、`git diff --check`

真实 MinIO、数据库和模型集成只有在对应服务实际启动并执行后才能声明验证通过。
