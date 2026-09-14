# Authentication Route Restore

计划版本：v0.2.0

状态：实施与验证完成。范围为 AM-ACCOUNT-007 的启动恢复和认证跳转，不修改后端 JWT 合同或登录页面样式。

## 实施

- `web/src/stores/useAuthStore.ts`：把现有 `restore()` 变成守卫可等待的认证结果；无 token
  返回未认证，持久化 token 通过 `/api/auth/me` 恢复用户，失败则调用现有 logout 清理。
  同一 token 的并发恢复复用一个 Promise，已恢复用户不重复请求。
- `web/src/router/index.ts`：全局守卫等待 `restore()` 后再决定 Login/受保护路由，避免
  失效 token 先放行 Chat。
- `web/src/views/AuthenticationView.vue`：删除只依据 accessToken 的 onMounted 跳转，
  登录成功后的 `openChat` 保持不变。
- ponytail：复用现有 Store、`/api/auth/me` 和唯一全局守卫，不增加认证插件、第二个守卫、
  View watcher或新的持久化字段。

## 验证

- 添加一个浏览器路由回归脚本，模拟无 token、有效 token、过期/401 token：验证受保护路由
  只在恢复成功后显示，失效 token 清除并停在 Login，Login 不产生循环，有效 token 进入 Chat。
- 执行相关 ESLint、typecheck、build 和 scoped diff check。测试使用模拟认证接口，不宣称真实
  后端或生产 JWT 联调。

## 验证结果（2026-09-14）

- `node test/auth-routing.mjs` 使用真实 Router、Pinia、App 和页面组件，通过 missing、expired、
  unauthorized、valid、valid-login 五种浏览器场景；失效认证从未渲染受保护导航。
- valid 场景额外模拟已恢复 token 到期后进入 Library，确认清除 token 并回到 Login，且不重复
  请求 `/api/auth/me`。测试接口为临时 Vite 内模拟响应，未连接真实后端。
- 相关 Store、Router、AuthenticationView 和回归脚本 ESLint 通过；typecheck、Vite build、
  git diff --check 通过。构建保留既有大 chunk 警告。
- 全仓 lint 仍被 `LibraryView.vue` 的既有未使用变量错误阻断，并报告其他文件 3 个既有 warning。
