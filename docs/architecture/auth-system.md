# Authentication System Architecture

## 1. Responsibility

认证系统负责邮箱密码登录、JWT 身份声明和受保护路由的用户解析，不负责具体业务功能的
授权编排。

## 2. Ownership

- `User.email` 是唯一登录账号。
- `User.uid` 是会话和 Agent Run 使用的稳定业务标识。
- JWT 的 `sub` 保存数字数据库用户 ID，同时携带 `uid`、`email` 和 `is_active`。
- `server/utils/auth.py` 负责密码哈希、JWT 创建/校验和用户查找。
- `AuthMiddleware` 只把可选 Bearer Token 解码结果放入
  `request.state.auth_payload`。
- 受保护路由通过 `AuthenticatedUser` 解析数据库用户，不在业务路由中重复实现认证。
- 平台管理权限由部署配置 `ADMIN_EMAILS` 拥有，按规范化邮箱匹配；`AdminUser` 在认证用户基础上返回 403，
  不把权限声明写入 JWT 或业务表。

## 3. HTTP Boundary

- `POST /api/auth/register`：注册账号。
- `POST /api/auth/login`：校验账号并签发 JWT。
- `GET /api/auth/me`：读取当前认证用户。

认证响应包含根据当前 `ADMIN_EMAILS` 计算的 `is_admin`，供前端隐藏管理入口；后端管理路由仍通过
`AdminUser` 独立强制授权，不能依赖前端可见性。

认证入口位于 `server/router/`；用户持久化和查询位于 `src/database/`。
认证系统不拥有 Conversation、Message 或 AgentRun 的业务状态。
