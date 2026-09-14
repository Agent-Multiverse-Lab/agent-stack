# Implementation Plan: Sidebar Account Navigation

计划版本：`v0.1.0`

## 1. Implementation Steps

1. 新增 `web/src/components/UserAvatarComponent.vue`，接收 `label` 和
   `size: "small" | "large"`，用 label 首字符渲染确定性占位 Avatar。
2. 新增 `web/src/components/SidebarAccountComponent.vue`，接收 `username`、
   `collapsed`，渲染展开/收起触发器和 Ant Design Vue Dropdown/Menu，
   并发出 `profile/settings/logout`。
3. 新增 `web/src/components/ProfileComponent.vue`，接收 `open`、`user`、
   `username`，只读展示 Avatar、占位 username、真实 email 和 Active/Inactive
   状态，通过 `close` emit 关闭。
4. 修改 `web/src/components/SettingsComponent.vue`，增加 `user` prop；Account
   section 使用真实 email 和状态，未登录时保留 Log in。
5. 修改 `web/src/views/NavigationView.vue`：在已登录时用
   `SidebarAccountComponent` 替换底部 Settings；持有 `profileOpen/settingsOpen`，
   处理子组件 emits；Logout 调用 Store 后跳转 Login；向 Profile/Settings 传入 user。
   不修改 Login 页面或品牌入口，不在这些位置接入 Avatar。
6. 保留 `web/src/router/index.ts` 的现有全局 access token 守卫，不增加 View 级
   重定向；验证直接进入 Chat/Knowledge 等受保护路由时无 token 会进入 Login，已有
   token 进入 Login 会返回 Chat。
7. 更新 `web/AGENTS.md` 的账户菜单和 Router 守卫职责，运行定向检查并核对桌面展开、
   桌面收起和移动 Sidebar；不启动 API 或 Worker。

## 2. Ownership

- Auth Store：access token、真实 `UserResponse` 和 logout 动作。
- `NavigationView`：账户入口的页面级组合、弹窗互斥和导航副作用。
- `SidebarAccountComponent`：账户触发器与菜单展示，不读取 Store/Router。
- `ProfileComponent` / `SettingsComponent`：各自 dialog 的展示和 close 事件。
- `UserAvatarComponent`：后端 Avatar 缺失期间的确定性占位展示。
- Login 页面与品牌入口：保持现状，不消费 `UserAvatarComponent`。
- `NavigationView`：在后端提供 username 前固定传入 `AM User` 占位文案。
- Router 全局守卫：每次导航时检查 access token 是否存在，统一拥有 Login 重定向。

## 3. Core Examples

### 3.1 Placeholder Avatar

目标：`web/src/components/UserAvatarComponent.vue`

```vue
<script setup lang="ts">
import { computed } from "vue"

const props = withDefaults(defineProps<{
  label?: string
  size?: "small" | "large"
}>(), {
  label: "AM User",
  size: "small"
})

const initial = computed(() =>
  props.label.trim().charAt(0).toUpperCase() || "A"
)
</script>
```

不接受 Avatar URL，不生成随机样式或用户对象。

### 3.2 Sidebar account contract

目标：`web/src/components/SidebarAccountComponent.vue`

```ts
defineProps<{
  username: string
  collapsed: boolean
}>()

const emit = defineEmits<{
  profile: []
  settings: []
  logout: []
}>()
```

```vue
<button type="button" aria-haspopup="menu">
  <UserAvatarComponent :label="username" />
  <span v-if="!collapsed">{{ username }}</span>
</button>
```

### 3.3 Parent coordination

目标：`web/src/views/NavigationView.vue`

```vue
<SidebarAccountComponent
  v-if="authStore.accessToken"
  username="AM User"
  :collapsed="sidebarCollapsed && !isNarrowViewport"
  @profile="openProfile"
  @settings="openSettings"
  @logout="logout"
/>

<ProfileComponent
  :open="profileOpen"
  :user="authStore.user"
  username="AM User"
  @close="profileOpen = false"
/>

<SettingsComponent
  :open="settingsOpen"
  :user="authStore.user"
  @close="settingsOpen = false"
/>
```

### 3.4 Logout

目标：`web/src/views/NavigationView.vue:logout`

```ts
const logout = async () => {
  profileOpen.value = false
  settingsOpen.value = false
  mobileSidebarOpen.value = false
  authStore.logout()
  await router.push({ name: "login" })
}
```

### 3.5 Route access guard

目标：`web/src/router/index.ts:router.beforeEach`

```ts
router.beforeEach((to) => {
  const hasAccessToken = Boolean(useAuthStore().accessToken)
  if (to.name === "login") return hasAccessToken ? { name: "chat" } : true
  return hasAccessToken ? true : { name: "login" }
})
```

现有守卫已满足该合同；实现阶段只验证，不创建第二个守卫或 View watcher。

## 4. Failure Handling

- token 恢复期间 `user` 为空时仍显示固定的 `A / AM User`，不阻塞 Sidebar。
- 用户恢复失败由现有 Auth Store 清理 token；账户入口随响应状态自然切回 Log in。
- Profile 没有用户时显示加载态，不构造虚假 email 或状态。
- Logout 的本地认证清理先于路由跳转；路由失败不恢复已清理 token。

## 5. Validation

```bash
cd web
npx eslint \
  src/components/UserAvatarComponent.vue \
  src/components/SidebarAccountComponent.vue \
  src/components/ProfileComponent.vue \
  src/components/SettingsComponent.vue \
  src/views/NavigationView.vue \
  src/router/index.ts
npm run typecheck
npx vite build
cd ..
git diff --check -- web docs/spec/product/account-navigation
```

视觉核对展开、收起和窄屏 Sidebar；确认 Profile/Settings 互斥、Escape/遮罩关闭、
菜单键盘操作、Logout 跳转，以及有/无 token 的入口重定向。
