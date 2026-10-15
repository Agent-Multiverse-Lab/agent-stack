# 平台配置生命周期

## 目标

把现有全局 Provider 内核接入应用启动和管理员 HTTP 边界，形成“预置补齐 → 管理员修改 → PostgreSQL 提交”闭环。

## 实施

1. Auth Domain 基于部署配置 `ADMIN_EMAILS` 提供可复用的管理员依赖；Provider 列表、详情、保存、发现和测试路由使用该依赖。
2. `model_router` 挂载 `settings_router`；`GET /api/models` 继续使用普通登录依赖。
3. FastAPI lifespan 在数据库初始化成功后打开事务会话，调用 `ensure_builtin_model_providers()`；补齐失败终止启动。
4. Qwen 预置使用与现有 Run 一致的 `provider_id=dashscope`。新增迁移把唯一的 `qwen` 行改名为 `dashscope`；两行同时存在时在修改前停止。
5. Settings 的 Models 导航只对管理员显示；供应商列表来自管理 API，详情草稿按 `provider_id` 保存在组件内存中。
6. 切换账号或退出时清空列表、草稿、Key 输入和操作结果，旧请求结果不能写入新账号状态。

## 事务与错误

- 预置先全量校验，再执行任何 INSERT。
- 保存成功以 PostgreSQL commit 为边界；缓存刷新属于提交后的独立步骤。
- 请求校验和远端错误通过 `ModelSettingsRoute` 转为脱敏响应，不回传输入 Key、目标地址或上游正文。

## 验证

- 启动首次插入、重复启动、已有配置保留、非法预置零写入、数据库失败中止。
- 普通用户全部管理接口返回 403，管理员请求进入 Service；未认证请求返回 401。
- 动态供应商列表、未知 Provider 图标回退、账号切换清理和迟到响应隔离。
- `qwen` 到 `dashscope` 的空表、单行、目标冲突和降级迁移。
