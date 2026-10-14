# 全局模型供应商预置与模型目录任务

- [x] M01（MODEL-PROVIDER-000）：按 `plan.md` 3.1.1～3.1.3 在 `src/model/providers/builtin.py` 定义两个纯字段 Preset 类和 DeepSeek/Qwen 实例；Service 显式映射字段、深拷贝 JSON 并复用 API DTO 完成全量校验，覆盖容器独立和重复定义，移除 Service 内的平行默认映射。
- [x] M02（MODEL-PROVIDER-001）：新增 `0015_model_provider_global` 迁移文件，安全合并语义相同的重复行，对冲突 Provider 要求显式 source 映射，再删除 `user_id` 并恢复 `provider_id` 主键；真实数据库迁移另行执行。
- [x] M03（MODEL-PROVIDER-000～001）：将 ORM、Repository、Service 和内部连接解析改为全局 `provider_id`，删除 user_id 参数；补齐入口保持显式调用，覆盖缺失插入、重复执行及已修改行保留。
- [ ] M04（MODEL-PROVIDER-005）：实现全局 `model:catalog:v3` 公开目录、严格解码、read-through、TTL、失效与提交后重建；目录只投影已启用模型且不含连接参数。
- [ ] M05（MODEL-PROVIDER-001～005）：接入管理员授权依赖；普通用户只读 `/api/models`，Provider 列表、详情、写入、发现和测试均仅管理员可用。
- [ ] M06（验收）：完成迁移、预置、全局 CRUD、授权、缓存生命周期和启动策略测试，并在可用环境验证 PostgreSQL 补齐与 Redis 预热。
- [ ] M07（MODEL-PROVIDER-000）：在接入切片将显式补齐入口接入 FastAPI lifespan，提交后预热全局目录，验证数据库失败中止和 Redis 失败不中止。

当前仅实施 Provider 内核；M04～M07 及前端接入在后续切片完成。Provider 管理路由暂未挂载，
Service 写入的 `cache_refreshed=false` 表示本切片尚未接入公开目录刷新。

`GET /api/models`、ModelContext 和 Run 校验由
[`chat-model-selection/tasks.md`](../../product/chat-model-selection/tasks.md) 承担；Settings 动态列表由
[`model-settings/tasks.md`](../../product/model-settings/tasks.md) 承担，避免在多个能力清单重复实施同一任务。
