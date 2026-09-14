# Specification: Sidebar Account Navigation

## 1. Purpose

将 Sidebar 底部的独立 Settings 按钮替换为统一账户入口。已登录用户在展开态看到
占位 Avatar 与显示名，收起态只看到同一个 Avatar；点击入口后通过子菜单进入
Profile、Settings 或 Log out。

当前后端 `UserResponse` 只提供 `id / uid / email / is_active`，没有 Avatar URL 或
username。本阶段固定使用 `AM User` 作为 username 占位文案，不修改后端合同。
Avatar 只用于 Sidebar 账户入口和 Profile；Login 页面、品牌入口及其他页面不展示账户
Avatar。

## 2. Requirements

### AM-ACCOUNT-001 Authenticated account entry

存在 access token 时，Sidebar 底部显示账户入口。展开态和移动端显示 Avatar 与显示名；
桌面收起态只显示 Avatar，并保持与展开态相同的 Avatar 尺寸和垂直位置。没有 access
token 时继续显示现有 Log in 入口，不显示账户菜单。

### AM-ACCOUNT-002 Placeholder identity

显示名固定为 `AM User`，Avatar 固定使用首字符 `A` 作为占位。该占位只用于 username
与 Avatar 展示；Profile 中的 email 和账户状态仍来自真实 `UserResponse`。不得加入
模拟头像 URL、随机颜色、假 email、假状态或新的后端字段。

### AM-ACCOUNT-003 Account menu

点击账户入口打开紧邻 Sidebar 的菜单，菜单按 `Profile`、`Settings`、`Log out` 排列。
菜单操作通过 emits 向父级报告，不直接读取 Router、Store 或页面弹窗状态。
`Log out` 的唯一可见入口是 Sidebar 底部 `AM User` 的账户菜单；Profile、Settings、
顶部菜单和其他页面不得重复提供 Logout 入口。

### AM-ACCOUNT-004 Component boundaries

- `UserAvatarComponent.vue` 只根据 `label` 和尺寸 prop 渲染占位 Avatar；
- `SidebarAccountComponent.vue` 拥有账户触发器和它的下拉菜单，接收 `username`、
  `collapsed` props，发出 `profile/settings/logout`；
- `ProfileComponent.vue` 接收 `open`、`user`、`username` props，发出 `close`，只读
  展示 Avatar、占位 username、真实 email 和真实账户状态；
- 现有 `SettingsComponent.vue` 继续拥有 Settings dialog，新增 `user` prop 以展示
  真实账户状态；
- `NavigationView.vue` 是协调所有者，持有 Profile/Settings 打开状态，响应 emits，
  调用 `authStore.logout()` 并导航到 Login。

Log out 是 Store 与 Router 动作，没有独立界面，不创建空的 `LogoutComponent`。

### AM-ACCOUNT-005 Modal exclusivity

Profile 和 Settings 不得同时打开。打开任一弹窗时关闭另一个；移动端选择菜单项后关闭
Sidebar。Log out 关闭账户相关弹窗和移动 Sidebar，清理认证状态后进入 Login。

### AM-ACCOUNT-006 Accessibility

账户触发器是原生 button，提供可识别的 account menu 名称和 `aria-haspopup="menu"`；
Avatar 是装饰内容。Profile 使用 dialog 语义、可访问标题、遮罩点击关闭和 Escape 关闭。
菜单项必须保持键盘可操作。

### AM-ACCOUNT-007 Route access guard

现有 `web/src/router/index.ts` 全局 `beforeEach` 是 Web 入口认证检查的唯一导航所有者。
首次进入或刷新页面时，守卫必须等待 Auth Store 恢复完成；Store 用 `/api/auth/me` 验证
持久化 access token 并恢复用户。只有 token 存在且验证成功才允许进入非 Login 路由；
没有 token、过期 token、格式错误 token或服务端返回 401 时，Store 清除本地认证状态，
守卫重定向到 `/login`，不得先渲染 Chat 或其他受保护页面。

访问 Login 时同样等待恢复：验证成功才重定向到 Chat，否则停留 Login。
`AuthenticationView` 不根据 token 字符串自行跳转；View 和 Component 不重复实现认证判断。
恢复只在当前 token 尚未验证时请求 `/api/auth/me`，同一 token 已恢复用户后不在每次导航
重复请求；access token 到期后再次进入路由或服务端认证失败时必须回到 Login。

## 3. Non-goals

- 不新增或修改后端 Avatar、username、Profile 更新或上传接口。
- 不创建 Avatar 上传、Profile 编辑、密码修改或账户删除能力。
- 不新增 Store、浏览器持久化、路由页面或第三方依赖。
- 不在 Login 页面、品牌 Logo 入口或其他导航入口增加 Avatar。
- 不重构完整 NavigationView 或 Settings 的其他 section。
- 不创建单独的 Logout component 或只转发 emits 的菜单包装层。

## 4. Acceptance Criteria

- 已登录展开态显示 Avatar 与固定 `AM User`，桌面收起态只显示同尺寸 Avatar。
- 未登录时保留 Log in，账户菜单不可见。
- 点击 Avatar 入口可选择 Profile、Settings 和 Log out。
- 全局只有 Sidebar 的 `AM User` 账户菜单提供可见的 Log out 入口。
- Profile 与 Settings 是独立组件且互斥显示；两者都通过 props/emits 与
  `NavigationView` 通信。
- Profile 只使用固定 `AM User` username、确定性占位 Avatar 和真实
  `UserResponse` email/status。
- Login 页面和品牌入口不显示账户 Avatar。
- Settings Account section 不再把已登录用户显示为 `Not logged in`。
- Log out 清理现有认证 Store 并进入 `/login`。
- 直接进入或切换到任何受保护路由时，没有 access token 会进入 `/login`；Login
  不产生重定向循环。刷新时持久化 token 必须先通过 `/api/auth/me` 验证；缺失、过期、
  格式错误或返回 401 的 token 不得短暂进入 Chat，也不得被 Login 页面再次送回 Chat。
- 没有新增 API、Store、依赖或模拟业务数据。
- 定向 ESLint、typecheck、Vite build 和 scoped diff check 通过。

### Chat 对话历史

导航链接下方提供可折叠的 Chat 分组，无额外分割线。登录后从真实线程列表接口分页加载，
独立滚动容器占据导航与账号区域之间的剩余高度，通过“加载更多”访问后续对话。
每行显示 title、当前对话高亮及右侧三点菜单，点击标题进入对应会话。
菜单提供重命名和确认删除，调用现有 PATCH/DELETE 接口；失败保留弹窗并显示服务端错误。
删除当前会话后进入新对话页，切换会话时刷新列表。折叠侧栏隐藏分组，移动侧栏展开时可用。
