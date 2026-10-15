# Chat 全局模型列表任务

- [x] C01（CHAT-MODEL-001）：按全局已启用 Provider 构建稳定的公开模型列表，覆盖展示字段、角色回退、空列表和协议工厂可用性。
- [x] C02（CHAT-MODEL-002）：使用全局 `model:chat:list:v3`，实现严格解码、TTL、hit/miss/损坏/失联回退及全局失效。
- [x] C03（CHAT-MODEL-001～002）：让 `GET /api/models` 保持登录认证并从全局 PostgreSQL Provider 回源，删除静态列表读路径。
- [x] C04（CHAT-MODEL-003、005）：更新 ModelContext 的账号切换、迟到响应、默认选择和空列表处理；ModelSelector 不按品牌白名单过滤，也不把模型列表写入浏览器持久化存储。
- [x] C05（CHAT-MODEL-004）：创建 Run 时从 PostgreSQL 校验模型 ID；Worker 按快照解析 Provider 连接并通过协议工厂创建 ChatModel。
- [x] C06（验收）：补齐模型列表/cache/API/Run/前端隔离测试，执行后端定向测试、typecheck、lint、test、build 和差异检查。
- [x] C07（CHAT-MODEL-004～005、AG-CONT-001）：实现会话 metadata / Agent config 模型绑定、创建 Run 时的模型快照与执行 Context 优先级；覆盖创建、继承、显式切换、配置变更隔离、子会话和前端详情恢复。
