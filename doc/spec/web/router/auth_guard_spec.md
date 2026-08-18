# 设计规范：前端未登录用户全局自动重定向至 /login

## 1. 预期行为 (Intended Behavior)
1. **未登录访问受保护路由重定向**：
   - 当用户未登录（`useAuthStore().accessToken` 为空）时，尝试访问任何受保护路由（如 `/`、`/c/:threadId`、`/library`、`/knowledge`、`/agent`、`/sandbox` 等）都将被全局路由守卫拦截，并自动重定向至 `/login` 登录页面。
2. **已登录访问 /login 自动返回主页**：
   - 当用户已经处于登录状态（`accessToken` 存在）时，再次访问 `/login` 将被自动重定向回主页 `/`。

## 2. 影响边界与公共契约 (Boundaries & Contracts)
- **目标修改文件**：`web/src/router/index.ts`
- **引入依赖**：`web/src/stores/useAuthStore.ts`
- **公共契约**：无破坏性变更。

## 3. 具体文件修改计划 (File Modification Plan)
1. `web/src/router/index.ts` (修改文件)：
   - 在 `export default router` 前加入全局导航守卫 `router.beforeEach((to, from, next) => { ... })`。
   - 读取 `useAuthStore` 中的 `accessToken` 校验登录凭证。
   - 未登录且访问非 `/login` 路径 -> `next({ name: "login" })`。
   - 已登录且访问 `/login` 路径 -> `next({ name: "chat" })`。

## 4. 验证方案 (Validation Approach)
- 运行 `cd web && npm run build` 执行 strict type check 与打包编译。
- 验证无 Token 时访问根路径及任意子路径均自动跳转至 `/login`。
