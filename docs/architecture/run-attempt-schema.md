# Run 执行尝试与租约

`AgentRun` 保存业务聚合状态（`agent_status`/结果/输出指针）；`AgentRunAttempt`
保存每次执行的持有者、心跳、租约与结束事实。Run 上的 `worker_id`/
`heartbeat_at`/`lease_expires_at` 是当前 owner 的查询快照，attempt 才是执行权
和租约的事实来源。

## 表结构

### `agent_run`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | `varchar(64)` | Run 主键 |
| `agent_status` | `varchar(32)` | 业务状态，终态不可回退 |
| `worker_id` | `varchar(128)` | 当前执行 owner 的快照，可空 |
| `heartbeat_at` | `timestamptz` | 当前 owner 最近一次成功续租时间，可空 |
| `lease_expires_at` | `timestamptz` | 当前 owner 租约到期时间，可空 |

### `agent_run_attempt`

| 字段 | 类型 | 可空 | 含义 |
| --- | --- | --- | --- |
| `id` | `varchar(64)` | 否 | attempt 主键，由认领方生成 |
| `run_id` | `varchar(64)` | 否 | 所属 Run；删除 Run 级联删除 |
| `attempt_no` | `integer` | 否 | Run 内递增序号，从 1 开始 |
| `worker_id` | `varchar(128)` | 否 | 本次执行 owner token |
| `status` | `varchar(32)` | 否 | `running`/`completed`/`failed`/`cancelled`/`interrupted`/`retry_released`/`lease_expired`/`orphaned` |
| `started_at` | `timestamptz` | 否 | 取得执行权时间 |
| `heartbeat_at` | `timestamptz` | 是 | 本 attempt 最近续租时间 |
| `lease_expires_at` | `timestamptz` | 是 | 本 attempt 租约到期时间 |
| `finished_at` | `timestamptz` | 是 | 结束时间；NULL 表示仍开放 |
| `error` | `text` | 是 | 错误摘要 |
| `error_type` | `varchar(64)` | 是 | 结构化错误分类 |

约束与索引：

- `UNIQUE (run_id, attempt_no)`：同一 Run 的尝试序号唯一
- 部分唯一索引 `uq_agent_run_attempt_one_open (run_id) WHERE finished_at IS NULL`：
  同一 Run 同时最多一条开放 attempt
- `(run_id, finished_at)` 与 `(finished_at, lease_expires_at)` 支持历史/过期查询

## 认领、续租与终态

1. `AgentRunRepository.set_running` 在 Run 行锁内检查状态/owner，关闭任何残留开放
   attempt，再通过 `AgentRunAttemptRepository.claim` 创建新 attempt；Run 写入
   owner/heartbeat/lease 快照。
2. `renew_lease` 先锁 Run 校验 owner 与 Run 级租约，再找到当前开放 attempt，
   由 `AgentRunAttemptRepository.renew` 校验 attempt owner/到期时间并更新心跳/租约；
   Run 快照同步更新。只有 `running` 续租；`cancel_requested` 立即停止续租，
   保留最后一次租约给当前 owner 完成取消收尾，超过租约由 reaper 收敛。
3. `set_agent_terminal` 在 Run 行锁内用 attempt 的 owner 和未过期租约做 fencing，
   写入 Run 终态并关闭 attempt；`release_for_retry` 关闭为 `retry_released`；
   过期巡检关闭为 `lease_expired`/`cancelled`。
4. `check_run_stopped(run_id, worker_id)` 判断当前 worker 是否仍可执行，返回
   `not_found`/`terminal`/`cancel_requested`/`attempt_missing`/`owner_mismatch`/
   `lease_expired`。`is_run_stopped` 是布尔入口。
5. 输出/审计写入通过 `lock_for_output_update`/`lock_output_persistence` 校验当前
   attempt 的 owner 与租约，过期 owner 不能写终态或输出。

## 迁移与兼容

- 历史结构：`0017_agent_run_attempt` → `0018_agent_run_attempt_no` →
  `0019_agent_run_lease`。
- `0022_agent_run_attempt_lease` 为 attempt 增加 `heartbeat_at`/
  `lease_expires_at`、过期索引和“一 Run 一开放 attempt”部分唯一索引；迁移会先把
  现存的多条开放 attempt 收敛为最新一条，其余标记 `orphaned`。
- 迁移前已认领、没有 attempt 的旧 Run 在终态/输出校验中退回 Run 级
  owner/租约；新认领一律创建 attempt，不再产生这种旧形态。
- 有已有数据库必须先执行 `uv run --no-sync alembic upgrade head`，再启动使用新
  ORM 的 API/Worker；`create_all` 不会给已有表补列。

## 验证

```bash
uv run --no-sync python -m pytest -q test/test_agent_run_lease.py \
  test/test_agent_run_repository.py test/test_agent_run_attempt_schema.py
```

SQLite 覆盖认领/续租/过期/终态/审计收敛；设置
`AGENT_STACK_SCHEMA_TEST_POSTGRES_URL` 后同一组结构测试在独立 PostgreSQL schema
中执行。真实 PostgreSQL 行锁竞争仍需在集成环境验证。
