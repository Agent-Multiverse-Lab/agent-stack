# Settings 全局模型供应商管理

计划版本：v0.2.0

## 1. 目标

保留已实现的 Settings 三栏布局和连接编辑交互，只替换供应商数据来源。
选项列不再声明 DeepSeek/Qwen 数组，而是向管理员展示全局 Provider 摘要响应。
供应商摘要、管理员身份变化、请求先后次序和未保存草稿继续由 `SettingsModels` 的 React 本地状态管理。

后端预置、启动补齐和 Redis 投影见
[`docs/spec/model/provider-management/plan.md`](../../model/provider-management/plan.md)。

## 2. 数据流

```text
管理员账号
  -> Auth Domain 管理员授权
  -> SettingsModels.loadProviders()
     -> GET /api/models/providers
        -> 后端读取全局 PostgreSQL Provider
  -> 选中第一项
     -> GET /api/models/providers/{provider_id}
        -> 后端读取全局 PostgreSQL 详情
        -> 初始化该 provider 草稿
```

保存继续调用现有 POST 接口。服务端再次验证管理员权限，保存成功后重读当前详情并更新组件中的摘要；
`cache_refreshed=false` 时告知用户数据库已保存、缓存刷新失败，不回滚草稿到保存前值。

## 3. 类型和图标

- `ModelProviderId` 不再是两个字面量的联合类型，改为符合后端 provider ID 约束的字符串。
- 供应商列表项的名称来自 `ModelProviderSummary.name`，不由 provider ID 在前端推测。
- 品牌图标映射只负责展示本地资产，不决定供应商是否存在。未知 ID 使用 Lucide `Bot` 中性图标。
- 动态列表为空时显示 Settings 内联空状态，详情列不发起请求。

## 4. 账号和并发边界

登录凭证或管理员权限变化时立即清空列表、详情、选中 ID、草稿、密钥输入和操作结果。
列表和详情请求在写入状态前比对身份版本与 provider ID；失去管理员权限后的迟到响应丢弃。
动态返回的 provider ID 仅用于已认证 API 路径，不用作 HTML 或 CSS 注入。

当前仓库尚无管理员角色。后端管理员授权合同是本计划的前置依赖；在该依赖完成前，前端不显示全局
Provider 管理入口，后端不得临时用普通 `AuthenticatedUser` 代替授权。

## 5. 验证

- 组件状态测试覆盖动态列表、空列表、管理员权限变化和迟到响应。
- 授权测试覆盖管理员可用以及普通用户列表、详情、保存、发现、测试均返回 403。
- 组件测试覆盖后端返回第三个供应商时自动出现，未知 ID 使用中性图标并可打开详情。
- 保留现有密钥不进入共享状态、换 URL 必须重新提供 Key、发现和连接检测测试。
- 执行 `npm run typecheck`、`npm run lint`、`npm test`、`npm run build` 和 `git diff --check`。
