# Chat 全局模型目录任务

- [ ] C01（CHAT-MODEL-001）：新增纯 `model_catalog` DTO/投影，按全局已启用 Provider 构建稳定的公开目录，覆盖展示字段、角色回退、空目录和静态 loader 可用性。
- [ ] C02（CHAT-MODEL-002）：将 Redis 收敛为全局 `model:catalog:v3`，实现严格解码、TTL、hit/miss/损坏/失联回退及全局失效。
- [ ] C03（CHAT-MODEL-001～002）：让 `GET /api/models` 保持登录认证并从全局 PostgreSQL Provider 回源，删除静态目录读路径和所有用户级缓存依赖。
- [ ] C04（CHAT-MODEL-003、005）：更新 ModelContext 的账号切换、迟到响应、默认选择和空目录处理；ModelSelector 不按品牌白名单过滤，也不把目录写入浏览器持久化存储。
- [ ] C05（CHAT-MODEL-004）：创建 Run 时按全局目录校验模型 ID，只允许 `is_available=true` 项；保持 metadata、BaseContext 和 Worker 静态 loader 合同不变。
- [ ] C06（验收）：补齐目录/cache/API/Run/前端隔离测试，执行后端定向测试、typecheck、lint、test、build 和差异检查。
- [x] C07（CHAT-MODEL-004～005、AG-CONT-001）：实现会话 metadata / Agent config 模型绑定、创建 Run 时的模型快照与执行 Context 优先级；覆盖创建、继承、显式切换、配置变更隔离、子会话和前端详情恢复。
