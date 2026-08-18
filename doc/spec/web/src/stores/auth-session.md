# 前端认证会话持久化

## 1. 目标

登录成功后刷新页面或重新打开浏览器，前端继续使用仍然有效的 Bearer Token，不因 Pinia
内存状态重建而丢失登录状态。Token 失效时清除本地认证状态，由用户重新登录。

## 2. 行为

1. `useAuthStore` 创建时从 `localStorage` 读取 `au.access_token`，立即恢复
   `accessToken`。
2. 存在 Token 时调用 `GET /api/auth/me` 获取当前 `UserResponse`，恢复 `user`。
3. 登录成功时同时更新 Pinia，并把 `access_token` 写入 `localStorage`。
4. `/api/auth/me` 校验失败时清空 Pinia 中的 `accessToken`、`user` 和本地 Token。
5. `logout()` 使用同一清理路径移除认证状态。

Pinia 仍然是页面运行期间的认证状态所有者；`localStorage` 只保存 Token，不保存用户对象。
后端现有 JWT 过期时间继续生效，不增加 Refresh Token 或前端续期逻辑。

## 3. 边界与公开合同

- 继续使用 `POST /api/auth/login` 返回的 `TokenResponse.access_token`。
- 恢复用户只调用现有 `GET /api/auth/me`，请求头为
  `Authorization: Bearer <access_token>`，响应沿用 `UserResponse`。
- 不修改后端认证接口、JWT 内容和有效期。
- 不改变 Thread、Message 或 Agent Run 合同；认证恢复后，现有
  `GET /api/chat/thread/{thread_id}` 可继续加载数据库中的会话。
- 不增加 Pinia 持久化插件或新的状态层。

## 4. 文件级修改计划

1. `web/src/api/auth.ts`
   - 增加调用 `GET /api/auth/me` 的认证 API 函数。
2. `web/src/stores/useAuthStore.ts`
   - 从 `localStorage` 初始化 Token；
   - 登录成功后写入 Token；
   - 使用 `/api/auth/me` 恢复用户；
   - 提供统一的 `logout()` 清理动作。

## 5. 验证

自动验证：

```bash
cd web
npm run typecheck
npm run lint
npm run build
cd ..
git diff --check -- web doc/spec/web/src/stores/auth-session.md
```

手动验证：

1. 登录后确认 `localStorage.au.access_token` 已写入。
2. 在 `/c/{threadId}` 刷新页面，确认用户状态和该会话消息能够恢复。
3. 删除或破坏本地 Token 后刷新，确认认证状态被清空。
4. 调用 `logout()` 后确认 Pinia 和 `localStorage` 中的认证状态同时清空。
