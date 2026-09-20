# 个人模型配置隔离
计划版本：v0.2.0

用户已要求将模型配置绑定到个人，按 MODEL-PROVIDER-001、005、006 实施。

1. `src/database/models.py::ModelProvider` 增加 User.id 外键，以 `(user_id, provider_id)` 为联合主键。
   新增 `0009_model_provider_user` 迁移，不修改已存在的 0008 迁移。若旧表非空，迁移仅接受显式
   `-x model_provider_owners=<JSON映射>`，验证完整归属后回填；无映射则写入前停止，不自动分配或删除数据。
2. `ModelRepository(session, user_id)` 在构造时绑定用户，全部查询包含用户条件；实例更新和删除校验所属用户。
   模型管理 Service 的所有持久化入口、远程请求和运行时解析必传 user_id，移除全局查询路径。
3. `src/model/model_cache.py` 使用带 user_id 的 v2 缓存键，写操作仅重建自己的目录。
4. `server/router/model_router.py` 从 current_user.id 传入服务；列表返回摘要，新增单供应商详情 GET。
   客户端伪造 body.user_id 被 DTO 拒绝，查询参数不参与所有权解析。
5. 前端实施路由见 `docs/spec/product/model-settings/plan.md` 的个人配置执行补充。
6. 用两个用户、同名供应商及不同密钥覆盖数据库、缓存、ASGI 路由、探测和运行时解析，验证跨账号迟到响应。

控制流示例：`GET /api/models/providers/deepseek` → `AuthenticatedUser.id=2` →
`get_provider(db, 2, 'deepseek')` → `WHERE user_id=2 AND provider_id='deepseek'`。
用户 1 的同名记录不参与读取；用户 2 未配置时返回 404。

最小性审查：复用现有用户表、模型表、缓存函数与服务；不新增角色系统、全局回退或第二套模型连接层。

## 凭据与出站安全

- `server/service/model_service.py::_settings_draft` 在 URL 改变时拒绝自动继承已有 Key，并清除草稿中的旧私有请求头；内部更新入口同样禁止隐式沿用 Key。
- `server/service/model_outbound.py::resolve_public_target` 校验全部 DNS 结果并返回固定 IP，`_request_json` 保留 Host / SNI、关闭代理及重定向。本轮不提供内网白名单例外。
- `server/router/model_router.py::ModelSettingsRoute` 负责认证后的脱敏错误映射，不把请求 scheme 当作模型测试结果；
  `web/src/api/model.ts` 将当前草稿交给后端 `/test`。生产 TLS 由部署入口负责。
- `src/database/credential_types.py` 使用 cryptography Fernet 加密 Key 与请求头，独立密钥通过服务端环境注入。
  `0010_model_credentials_encrypted` 仅在 0009 确认归属后转换历史凭据；未配置有效密钥则在写入前停止。
- 前端请求体不做自定义加密：生产部署由 TLS 保护传输，服务端认证和加密保护数据库。测试覆盖密文存储、跨用户访问、凭据转发、DNS 混合结果及固定 IP 请求。

设计依据：[OWASP TLS](https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Security_Cheat_Sheet.html)、
[OWASP SSRF](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)、
[HTTPX SNI 扩展](https://www.python-httpx.org/advanced/extensions/)、
[Fernet](https://cryptography.io/en/stable/fernet/)。

## 验证结果与上线条件

- 43 项模型服务、仓储、缓存、用户隔离、路由、迁移和安全测试通过；测试数据全部为临时 SQLite / 模拟 HTTP 数据。
- 前端构建和修改文件 ESLint 通过，后端改动 Ruff 通过；构建保留既有的大 chunk 提示。
- 浏览器 HTTPS 测试 origin / 模拟 API 验证：列表与详情缓存复用、切换时才加载详情、Key 不进入 Store、换账号清空、旧账号迟到响应被丢弃、退出后缓存清空。此测试不代表真实部署证书或真实厂商联调。
- 依赖锁文件已更新，cryptography 成为直接依赖。真实数据库、真实凭据、访问日志均未读取或迁移，未部署服务。

部署顺序：

1. 通过服务端密钥管理系统提供独立的 `MODEL_CREDENTIAL_KEY`（Fernet 格式），保留可恢复备份；不要放在前端、仓库或日志中。
2. 通过 HTTPS 提供页面与 API。若在可信反向代理终止 TLS，只允许明确的代理地址传递协议头；业务路由不直接接受客户端伪造的 X-Forwarded-Proto。
3. 按用户已确认的处理方式保留旧全局数据，取得每个旧 provider_id 对应的 User.id 后再提供迁移映射；缺少映射或加密密钥会停止，不能跳过检查。
4. 在有实际基础设施的环境执行 Alembic 升级及后端/Worker 重建，再验证真实 HTTPS 模型连接。本轮禁止所有内网目标，包括本地 Ollama、vLLM 地址。

本轮不变更 Chat 现有静态目录及模型实例构造调用链；个人配置的内部解析入口现在必传 user_id，后续接入该调用链时必须使用受控出站传输。
