# Specification: Chat Agent Tool Group

## 1. Purpose

将后端 Agent 状态事件中的 Todo 列表展示为对话内的顶层 Tool Group，替换当前仅显示
“Agent state updated”的临时卡片。组件采用紧凑、可展开的行式布局。

## 2. Requirements

### CHAT-TOOL-001 Event boundary

组件直接读取 Tool Message 的 `event.agent_state.agent_todo`。每个 Todo 仅使用后端提供的
`content` 和 `status`；支持的状态严格为 `pending | in_progress | completed`。

### CHAT-TOOL-002 Group composition

`AgentToolGroupComponent` 是对话渲染中的顶层 Tool 组件。组标题展示真实 Todo 数量与完成
数量，组内每行展示状态图标、状态名称和 Todo 内容，并允许展开查看该项的真实原始数据。

### CHAT-TOOL-003 Status presentation

- `pending` 使用静态未开始图标；
- `in_progress` 使用旋转中的执行图标；
- `completed` 使用完成图标。

未知或格式错误的条目不得被映射成虚构状态。

### CHAT-TOOL-004 Current integration

`ChatMessageComponent` 对 `payload.type === "tool"` 的消息渲染
`AgentToolGroupComponent`。旧 `AgentToolComponent` 及其未被真实事件使用的
`running | completed | failed` 前端状态模型被删除，不保留兼容入口。

### CHAT-TOOL-005 Data integrity

不得迁移参考示例中的静态工具列表、文件 diff、计时推进、模拟消息或假详情。没有有效
Todo 时，组件只展示空状态，不构造替代数据。

## 3. Non-goals

- 不修改后端 Agent state、Run/SSE 事件协议或 Todo middleware。
- 不从 Agent Todo 推断真实 tool call、文件修改或命令输出。
- 不聚合 Thinking、Assistant 文本或 Human approval 消息。

## 4. Acceptance Criteria

- Tool Message 在对话中由独立的顶层 Agent Tool Group 渲染。
- 三种真实 Todo 状态具有可辨识的视觉反馈。
- 分组、条目标题和展开详情均只来自当前事件。
- 旧 Agent Tool 组件和废弃类型被移除。
- TypeScript、定向 ESLint、构建与 diff 检查通过。
