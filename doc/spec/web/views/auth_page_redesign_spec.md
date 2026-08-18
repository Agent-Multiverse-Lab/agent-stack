# 设计规范：AuthenticationView 与 LoginComponent 登录页高品质重构 (整体下移与黄金垂直视觉平衡)

## 1. 预期行为 (Intended Behavior)
1. **右侧表单整体平移下调 (Form Vertical Balance Downwards)**：
   - 将 [AuthenticationView.vue](file:///home/leejuju/projects/multi-agent-s2c/web/src/views/AuthenticationView.vue) 右侧卡片的顶端间距从原先较紧凑的 `pt-6` 调大平移至 **`pt-[76px]`**。
   - **效果**：表单标题（"Welcome back"）、Email 框、Password 框、提交按钮（"Sign In"）及底栏文本整体向下平移，呈现黄金比例的居中偏上位置，消除顶部偏高的视觉失衡。
2. **保持固定 Email/Password 位置与 520ms 顺滑下推动画**：
   - 切换注册模式时，"Ensure your password" 框继续以 520ms 缓缓下推底栏，顶部标题与输入框在下移后的新锚点位置固定不动。

## 2. 影响边界与公共契约 (Boundaries & Contracts)
- **受影响视图**：`web/src/views/AuthenticationView.vue`
- **受影响组件**：`web/src/components/LoginComponent.vue`
- **契约兼容性**：无破坏性变更。

## 3. 具体文件修改计划 (File Modification Plan)
1. `web/src/views/AuthenticationView.vue` (修改文件)：
   - 将内层表单包裹容器由 `pt-6` 调整为 `pt-[76px]`。

## 4. 验证方案 (Validation Approach)
- 运行 `cd web && npm run build` 执行 strict type check 与打包编译。
- 验证表单整体下移后的视觉平衡感。
