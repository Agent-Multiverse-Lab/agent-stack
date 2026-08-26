# Plan: Chat Thinking Group

计划版本：v0.1.0

## 1. Implementation

1. 新增 `web/src/components/chat/loading/ChatThinkingIconComponent.vue`，迁移现有 3×3
   像素延迟计算和 `pixel-on` 动画。
2. 修改 `ChatLoadingStateComponent.vue`，复用 icon 组件并保留现有 label、计时和
   shimmer 文案。
3. 新增 `ChatThinkingGroupComponent.vue`，负责标题、计时、可选 slot 和展开状态。
4. 修改 `ChatView.vue`，只把 Run 活跃期间的 Thinking 占位替换为 Group；Conversation
   加载入口保持 `ChatLoadingStateComponent`。

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
- `.\node_modules\.bin\eslint.cmd --no-warn-ignored src/components/chat/loading/ChatThinkingIconComponent.vue src/components/chat/loading/ChatThinkingGroupComponent.vue src/components/chat/loading/ChatLoadingStateComponent.vue src/views/ChatView.vue`
- `git diff --check -- web docs/spec/product/chat-thinking docs/spec/README.md`
