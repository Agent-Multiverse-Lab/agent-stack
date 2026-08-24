# Tasks: Sidebar Account Navigation

## Task Map

| Task ID | 关联需求 | 主要文件 | 说明 |
| --- | --- | --- | --- |
| AM-AC01 | AM-ACCOUNT-002/004/006 | `web/src/components/UserAvatarComponent.vue` | 用固定 username label 派生占位 Avatar |
| AM-AC02 | AM-ACCOUNT-001/003/004/006 | `web/src/components/SidebarAccountComponent.vue` | 实现响应收起状态的账户触发器和菜单 emits |
| AM-AC03 | AM-ACCOUNT-002/004/006 | `web/src/components/ProfileComponent.vue` | 实现只读 Profile dialog |
| AM-AC04 | AM-ACCOUNT-004 | `web/src/components/SettingsComponent.vue` | 通过 user prop 展示真实账户状态 |
| AM-AC05 | AM-ACCOUNT-001/003/005 | `web/src/views/NavigationView.vue` | 组合账户入口、互斥弹窗和 logout 导航 |
| AM-AC06 | AM-ACCOUNT-004 | `web/AGENTS.md` | 记录账户组件与协调所有权 |
| AM-AC07 | AM-ACCOUNT-007 | `web/src/router/index.ts` | 验证现有全局 access token 守卫覆盖所有入口 |
| AM-AC08 | AM-ACCOUNT-001/003/005/006/007 | `web/` | 验证展开、收起、移动端、键盘、重定向与构建 |

## Done Conditions

- Sidebar 展开态显示 Avatar + 显示名，收起态显示同尺寸 Avatar。
- 菜单只有 Profile、Settings、Log out 三项。
- Log out 的唯一可见入口位于 Sidebar 的 `AM User` 菜单，其他组件和页面不重复展示。
- Avatar、账户入口、Profile 和 Settings 均由独立组件拥有真实展示职责。
- 组件通过 typed props/emits 通信，不直接跨组件修改状态。
- 后端缺少 Avatar/username 时固定显示 `AM User / A`；email/status 仍使用真实数据。
- `UserAvatarComponent` 只被 Sidebar 账户入口和 Profile 使用，Login 与品牌入口不接入。
- Logout 保持为 Store/Router action，不创建空组件。
- access token 入口检查只由 Router 全局守卫拥有，不在 View/Component 重复实现。
- 未增加后端字段、API、Store、依赖、路由页面或持久化。
- 计划中的验证命令已执行并如实报告。
