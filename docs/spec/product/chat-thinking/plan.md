# Plan: Chat Thinking Group

计划版本：v0.1.0

## 1. Implementation

1. 新增 `web/src/components/chat/loading/ChatThinkingIcon.vue`，迁移现有 3×3
   像素延迟计算和 `pixel-on` 动画。
2. `ChatThinkingGroupComponent.vue` 直接负责 icon、label、计时、shimmer、可选 slot
   和展开状态；删除只做中转的 `ChatLoadingStateComponent.vue`。
3. 修改 `ChatView.vue`，Conversation 加载和 Agent Thinking 都直接使用 Thinking
   Group；在当前 Run 首个 Tool 状态之前显示 Thinking，并把 Tool 消息
   作为独立的同级紧凑组件保留；Assistant 正文或等待用户交互只卸载 Thinking，不卸载
   Tool 组件。

## 2. Component contracts

目标：`web/src/components/chat/loading/ChatThinkingGroupComponent.vue`

```vue
<ChatThinkingGroupComponent label="Thinking">
  <!-- 后续由真实事件提供的可选详情 -->
</ChatThinkingGroupComponent>
```

无默认 slot 时组件不展示 chevron。组件挂载后从零开始显示耗时，卸载时清理 timer。

## 3. Validation

- `npm.cmd run typecheck`
- `.\node_modules\.bin\eslint.cmd --no-warn-ignored src/components/chat/loading/ChatThinkingIcon.vue src/components/chat/loading/ChatThinkingGroupComponent.vue src/views/ChatView.vue`
- `git diff --check -- web docs/spec/product/chat-thinking docs/spec/README.md`
