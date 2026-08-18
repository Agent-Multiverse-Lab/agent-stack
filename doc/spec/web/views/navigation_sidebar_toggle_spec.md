# 设计规范：SearchChatComponent 弹窗宽度微调 (-100px 适中黄金比例)

## 1. 预期行为 (Intended Behavior)
1. **SearchChatComponent 弹窗宽度精细微调**：
   - 弹窗宽度在上一版的基础上 **减小 100px**：从 `1080px` 调整为 **`w-[min(84vw,980px)]` (最大宽度 980px)**。
   - 弹窗高度同步收拢为 **`h-[min(60vh,620px)]`**，形成视觉比例更加和谐舒适的“适中大屏”检索弹窗。
   - 保持横条搜索框（`px-6 py-4.5`、`text-base`）与纯标题对话列表的高清晰呈现。

## 2. 影响边界与公共契约 (Boundaries & Contracts)
- **目标修改组件**：`web/src/components/SearchChatComponent.vue`
- **公共契约**：无破坏性变更。

## 3. 具体文件修改计划 (File Modification Plan)
1. `web/src/components/SearchChatComponent.vue` (修改文件)：
   - 调整外层 Modal 容器尺寸：`w-[min(84vw,980px)] max-w-[980px] h-[min(60vh,620px)]`。

## 4. 验证方案 (Validation Approach)
- 运行 `cd web && npm run build` 执行 strict type check 与打包编译。
- 验证调整后的 980px 宽度弹窗比例与阅读舒适度。
