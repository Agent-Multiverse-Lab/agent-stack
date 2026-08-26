# Plan: Chat Agent Tool Group

计划版本：v0.1.0

## 1. Implementation

1. 新增 `web/src/components/chat/tools/AgentToolGroupComponent.vue`，在组件内校验
   `event.agent_state.agent_todo`，并基于真实 `content/status` 生成分组摘要与状态行。
2. 修改 `web/src/components/chat/ChatMessageComponent.vue`，把 Tool Message 的内联临时
   卡片替换为顶层 Group 组件。
3. 删除 `web/src/components/chat/AgentToolComponent.vue`，同时删除
   `web/src/types/chat.ts` 中仅供旧组件使用的状态类型。

## 2. Component contract

目标：`web/src/components/chat/tools/AgentToolGroupComponent.vue`

```vue
<AgentToolGroupComponent :event="message.payload.event" />
```

组件不接受二次转换后的 Tool view model；它负责在渲染边界安全读取后端事件。

## 3. Validation

- `npm.cmd run typecheck`
- 定向 ESLint 检查新增组件、消息组件和 chat 类型
- `npm.cmd run build`
- `git diff --check`
