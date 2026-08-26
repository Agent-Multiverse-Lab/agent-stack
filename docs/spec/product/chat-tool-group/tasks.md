# Tasks: Chat Agent Tool Group

## Ordered work

1. 锁定 `agent_state.agent_todo` 的真实字段和三种状态。
2. 实现可折叠的顶层 Group 与逐项状态展示。
3. 接入对话 Tool Message 分支。
4. 删除旧组件及其孤立类型。
5. 执行 TypeScript、ESLint、构建和 diff 检查。

## Done Conditions

- 不存在静态演示 Tool、diff 或模拟状态推进；
- Todo 项只使用 `content` 与 `status`；
- 无有效 Todo 时显示明确空状态；
- `AgentToolComponent.vue` 不再存在且无残留引用；
- 定向检查通过并如实报告。
