# Library 页面前端设计与实现规格 (Revision 3)

## 目标行为

### 1. Library 视图无嵌套布局与 Hover 容器 (Flat Borderless Layout with Hover Containers)
- **非嵌套显示**：默认状态下不使用重叠卡片或嵌套实线容器，列表行与页面呈扁平无缝平铺。
- **Hover 显隐容器**：当鼠标悬停 (Hover) 在列表行或交互元素上时，才动态显现圆角背景容器与微边框（如 `hover:bg-mist/60 hover:rounded-lg`）。
- **居中视口**：页面内容限制在中间区域 (`max-w-[920px] mx-auto`)，左右两侧自然留空。

### 2. Login 入口与已登录状态控制 (LoggedIn State Handling)
- 关联 `useAuthStore()` 校验当前用户登录状态 (`user` / `accessToken`)。
- 当用户**已登录**时：
  - 侧边栏底部与右上角的 "Log in" 按钮直接隐藏 / 替换为用户状态。
  - 若用户在已登录状态下直接访问 `/login` 路由，系统将自动重定向至主页 `/`。

---

## 字符布局设计图 (ASCII Layout Diagram)

```text
+-----------------------------------------------------------------------------------+
|  [Left Margin]                      [Center Column: 920px]         [Right Margin] |
|                                                                                   |
|  (1) 头部栏 (Header Row):                                                          |
|  [Library Icon] Library                                     [ Search (R:16px) ]  |
|                                                     [+ Upload] [+ Folder] [+ Note]|
|-----------------------------------------------------------------------------------|
|  (2) 工具筛选栏 (Collapsible Filter Toolbar):                                      |
|  [⚙ Filters & Tabs v] (Hover/Click 展开 popover)            [≡ List] [:: Grid]   |
|-----------------------------------------------------------------------------------|
|  (3) 列表视图 (List View - 默认展示 3 列, Hover 时高亮显示卡片容器):              |
|                                                                                   |
|  FILE NAME                             FILE CREATED TIME                FILE SIZE |
|  -------------------------------------------------------------------------------- |
|  [hover state] 📄 Hero_Banner_v2.png    2026-08-11 11:20                 3.4 MB  |  <-- Hover 时才显示 hover:bg-mist 圆角容器
|  -------------------------------------------------------------------------------- |
|  [normal state] 📂 Design Assets        2026-08-10 09:15                   --     |  <-- 平常无边框/无背景
|  -------------------------------------------------------------------------------- |
|  [normal state] 📝 Meeting Notes        2026-08-01 11:45                 2.3 KB  |
|                                                                                   |
|  ... (无限滚动 触底懒加载 sentinel)                                               |
+-----------------------------------------------------------------------------------+
```

---

## 文件修改计划

1. `web/src/views/LibraryView.vue` & `LibraryFileListComponent.vue`
   - 去掉外层 table 描边与硬卡片嵌套，列表行使用无缝 flex/grid 项，`hover:bg-mist/60 hover:rounded-[12px]` 实现悬浮容器效果。
2. `web/src/views/NavigationView.vue` & `web/src/views/AuthenticationView.vue`
   - 接入 `useAuthStore()`，当 `authStore.user` 或 `accessToken` 存在时隐藏 "Log in" 按钮；访问 `/login` 时自动跳转主页。
