# Specification: Chat Thinking Group

## 1. Purpose

将对话运行中的 Thinking 状态收口为 Vue 原生组合组件，同时保留现有 3×3 像素
图标及其错峰流动动画。该能力只调整 Web 对话页的运行中视觉反馈。

## 2. Requirements

### CHAT-THINK-001 Pixel flow icon

`ChatThinkingIconComponent` 使用 3×3 像素矩阵。九个像素继续根据行列位置设置不同
动画延迟，并使用现有 `pixel-on 650ms ease-in-out infinite` 流动效果。不得替换为
星形图标、普通 spinner 或静态图片。

### CHAT-THINK-002 Group composition

`ChatThinkingGroupComponent` 组合 Thinking icon、状态文案、运行耗时和可选的默认
slot。存在 slot 内容时允许用户展开或收起；无 slot 内容时只展示状态标题，不渲染
无效的展开按钮。

### CHAT-THINK-003 Current integration

`ChatView` 在 Run 活跃且当前 Run 尚无 Assistant 文本时展示 Thinking Group。
Conversation 加载状态继续使用 `ChatLoadingStateComponent`，该组件复用相同的 Thinking
icon，不维护第二套像素动画。

### CHAT-THINK-004 Event boundary

本能力不新增前端 `thinking` 消息类型，不修改 Run/SSE 事件协议，也不使用演示代码中的
静态阶段、模拟计时序列或 Steps/Reasoning/Search/Coding 假数据。Group 的可选 slot
用于承载后续真实事件内容。

### CHAT-THINK-005 Accessibility

运行状态使用 `role="status"` 和 `aria-live="polite"`。展开按钮必须暴露
`aria-expanded`；系统启用减少动态效果时，像素保持可见但停止循环动画。

## 3. Non-goals

- 不修改后端、数据库、Run 生命周期或事件结构。
- 不聚合当前 `text | tool` Message，也不把 Tool Message 伪装成 Thinking 内容。
- 不迁移 React 示例或引入新的动画依赖。

## 4. Acceptance Criteria

- 运行中 Thinking 状态继续显示 3×3 像素流动效果。
- Thinking Group 以独立 Vue 组件存在，并组合独立 icon 组件。
- Conversation 加载和 Thinking Group 复用同一个 icon 组件。
- `npm run typecheck`、定向 ESLint 和 `git diff --check` 通过。
