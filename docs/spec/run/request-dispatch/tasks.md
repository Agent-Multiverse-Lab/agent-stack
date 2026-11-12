# 请求持久化与派发任务

## 实施

- [x] 添加只保存标识与输入关联的 `AgentRunRequest`、Repository 和 `0028_agent_run_request` 迁移。
- [x] 在 `server/service/agent_run_service.py` 定义并组装 `AgentRunRequestInput`，复用 Request 和锁定后的 Conversation，DAO 返回 ORM 记录。
- [x] 拆分接收与 Run 创建事务，在两次事务中分别锁定会话。
- [x] 接入重复请求复用、忙碌与待回答问题返回 409、输入消息关联及提交后入队。
- [x] 按事务边界保留请求、消息和附件，复用已有入队失败终态写入。
- [x] 核对 Router 响应并同步设计、Run 架构和持久化所有权文档。

## 验证

- [x] 46 项本地测试通过：Service、Run Repository、请求 Repository、附件与 SQLite 迁移升级/回退。
- [x] Ruff 和 `git diff --check` 通过。
- [x] 使用 Python `compile(..., 'exec')` 完成 208 个后端、迁移和测试文件的语法编译检查。
- [ ] PostgreSQL 跨会话可见性、并发锁竞争及迁移集成测试：连接阶段断开，用户确认暂缓。

本地验证命令：

```powershell
.\.venv\Scripts\python.exe -m unittest test.test_agent_run_service test.test_agent_run_repository test.test_agent_run_request_dispatch.AgentRunRequestRepositoryTest test.test_attachment_service -q
```

数据库配置可用后执行：

```powershell
$env:RUN_REQUEST_DISPATCH_TEST = '1'
.\.venv\Scripts\python.exe -m unittest test.test_agent_run_request_dispatch.AgentRunRequestDispatchTest -v
```

集成测试只创建并清理随机命名的独立 schema。业务库尚未执行迁移。
`compileall` 的缓存写入因本机目录权限失败，改用不写缓存的内存编译验证；
包含 Worker 导入的扩大回归在导入阶段耗时未完成，未计入通过数量。
