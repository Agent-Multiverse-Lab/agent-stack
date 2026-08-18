# Chat Action Menu 组件设计规范（V3 - 根据输入框位置上下展开）

## 1. 概述与需求

`ChatActionMenuComponent` 展开为与输入框等宽（`w-full`）、圆角为 `16px`（`rounded-[16px]`）的操作面板。展开方向由输入框在页面中的位置决定：

- 空会话中，输入框位于页面中部，面板在输入框下方展开；
- 会话开始后，输入框停靠页面底部，面板在输入框上方展开。

初始面板包含一个动作卡片/行：“添加附件”，带 `Paperclip` 图标。

## 2. 组件结构与定位设计

### `ChatActionMenuComponent.vue`
- **容器定位**：挂载在 `ChatMessageInputComponent.vue` 的 `form` 输入框容器内，以输入框为定位上下文。
- **位置合同**：接收 `placement: "top" | "bottom"`；不自行测量视口或推断页面状态。
- **外观与尺寸**：
  - `bottom`：`absolute top-full left-0 right-0 mt-2 z-50`
  - `top`：`absolute bottom-full left-0 right-0 mb-2 z-50`
  - **宽度**：`w-full`（与输入对话框 100% 等长）
  - **圆角**：`rounded-[16px]` (即 `border-radius: 16px`)
  - **背景与边框**：`border border-graphite/14 bg-paper/95 shadow-lg backdrop-blur-md p-2`
- **菜单项布局**：
  - 选项条目具备 rounded-[12px] 悬浮背景效果，包含 `Paperclip` 图标、标题文字“添加附件”。
- **触发器提示**：加号图标按钮使用 Ant Design Vue `ATooltip`，标题为
  `Action menu`；Tooltip 位于操作面板展开方向的相反一侧。

### `ChatMessageInputComponent.vue` 对接
- `form` 容器需保持 `relative` 定位；
- 接收 `actionMenuPlacement: "top" | "bottom"`，并原样传给 `ChatActionMenuComponent`；
- 加号按钮触发 `ChatActionMenuComponent` 的开合；
- 点击面板内的“添加附件”选项后关闭面板，并触发出原生的 `fileInput?.click()`；
- 选中的文件上传后，依然在输入框顶部/内部通过 `AttachmentComponent.vue` 呈现。

## 3. 修改计划

1. **更新 View**：`web/src/views/ChatView.vue`
   - 根据现有 `composerDocked` 向输入组件传递 `top` 或 `bottom`，不新增第二份停靠状态。
2. **更新组件**：`web/src/components/chat/ChatMessageInputComponent.vue`
   - 声明 `actionMenuPlacement` prop，并传给 `ChatActionMenuComponent`。
3. **更新组件**：`web/src/components/chat/ChatActionMenuComponent.vue`
   - 声明 `placement` prop，并分别使用上方或下方定位类；
   - 面板过渡的纵向位移方向与展开方向一致；
   - 使用现有 `ATooltip` 包装加号图标按钮。

## 4. 验证计划

```bash
cd web
npm run typecheck
npm run lint
npm run build
```
- 确认空会话时面板在输入框下方以 100% 等宽形式展开；
- 确认输入框停靠底部后，面板在输入框上方以 100% 等宽形式展开；
- 确认面板边框圆角为 `16px`（`rounded-[16px]`）；
- 确认点击“添加附件”正常呼起文件选择窗口，上传后依然由 `AttachmentComponent` 渲染。
- 确认加号按钮在悬停和键盘聚焦时显示 `Action menu` Tooltip，且不遮挡展开面板。
