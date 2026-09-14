# Specification: Chat Agent Tool Group

## 1. Purpose

将后端 Agent 状态事件中的 Todo 列表展示为对话内的顶层 Tool Group，替换当前仅显示
“Agent state updated”的临时卡片。组件采用紧凑、可展开的行式布局。

## 2. Requirements

### CHAT-TOOL-001 Event boundary

组件直接读取 Tool Message 的 `event.agent_state.agent_todo`。每个 Todo 仅使用后端提供的
`content` 和 `status`；支持的状态严格为 `pending | in_progress | completed`。

### CHAT-TOOL-002 Group composition

`AgentToolGroupComponent` 展示真实 Tool Message 内容。它紧随当前 Run 的 Thinking，
作为独立的同级紧凑组件出现；组标题展示真实 Todo 数量与完成数量，组内每行
展示状态图标、状态名称和 Todo 内容，并允许展开查看该项的真实原始数据。

### CHAT-TOOL-003 Status presentation

- `pending` 使用静态未开始图标；
- `in_progress` 使用旋转中的执行图标；
- `completed` 使用完成图标。

未知或格式错误的条目不得被映射成虚构状态。

### CHAT-TOOL-004 Current integration

`ChatMessageComponent` 对 `payload.type === "tool"` 的消息渲染
`AgentToolGroupComponent`；`ChatView` 负责让当前 Run 的 Tool Message 紧随 Thinking
并保持独立生命周期。旧 `AgentToolComponent` 及其未被真实事件使用的
`running | completed | failed` 前端状态模型被删除，不保留兼容入口。

### CHAT-TOOL-005 Data integrity

不得迁移参考示例中的静态工具列表、文件 diff、计时推进、模拟消息或假详情。没有有效
Todo 时不渲染 Tool Group，也不构造替代数据。
同一 Run 的新 Agent state 覆盖旧快照，不把完整状态历史堆叠到详情区。
如果新快照不含有效 Todo，则移除该 Run 先前的 Agent state 组件。

## 3. Non-goals

- 不修改后端 Agent state、Run/SSE 事件协议或 Todo middleware。
- 不从 Agent Todo 推断真实 tool call、文件修改或命令输出。
- 不聚合 Assistant 文本或 Human approval 消息。
- 当前事件合同尚未提供多个独立 Tool Call，本能力不预建对应的收纳层。

## 4. Acceptance Criteria

- 当前 Run 的有效 Tool Message 在 Thinking 下方同级渲染，不额外缩进。
- 空 Todo 不渲染；正文输出和 Run 结束后当前页面的 Tool Group 仍然保留。
- 三种真实 Todo 状态具有可辨识的视觉反馈。
- 分组、条目标题和展开详情均只来自当前事件。
- 旧 Agent Tool 组件和废弃类型被移除。
- TypeScript、定向 ESLint、构建与 diff 检查通过。
