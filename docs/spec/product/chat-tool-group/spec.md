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

- Agent state 快照继续沿用现有 Run/SSE 协议。
- 不从 Agent Todo 推断真实 tool call、文件修改或命令输出。
- 不聚合 Assistant 文本或 Human approval 消息。
- 工具调用只展示真实记录，不生成模拟调用。

## 4. Acceptance Criteria

- 当前 Run 的有效 Tool Message 在 Thinking 下方同级渲染，不额外缩进。
- 空 Todo 不渲染；正文输出和 Run 结束后当前页面的 Tool Group 仍然保留。
- 三种真实 Todo 状态具有可辨识的视觉反馈。
- 分组、条目标题和展开详情均只来自当前事件。
- 旧 Agent Tool 组件和废弃类型被移除。
- TypeScript、定向 ESLint、构建与 diff 检查通过。

## 5. 工具调用历史与展示

真实工具调用（包括 `write_todos`）由 AI Message 的 `tool_calls` 写入 `tool_call` 表，
对应 ToolMessage 更新结果与成功/错误状态。取消或异常退出时保存已完成 checkpoint 步骤。
会话详情加载 Message 时预加载 ToolCall，并按工具记录 ID 排序返回 `tool_calls`。
前端运行中按流事件更新工具；加载历史时使用持久化调用参数、结果和状态，并按
“所属 AI 消息正文 → 该消息的工具调用 → 下一条 AI 消息”恢复顺序。
同一 tool_call_id 的数据库记录替换内存卡片，避免重复；切换会话后不依赖旧组件内存恢复工具。

工具行依次展示状态图标、工具名称和状态标签；展开按钮置于右侧。
外层使用圆角卡片，展开后呈现参数、执行进度、结果或错误。
Todo 状态快照与 `write_todos` 工具执行记录属于不同数据，不以快照伪造工具记录。
