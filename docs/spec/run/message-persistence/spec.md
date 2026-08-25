# Agent Run Message Persistence Spec

## 1. Purpose

在 Agent Stream 正常结束后，从 LangGraph 最新 checkpoint state 的 `messages` 中
读取 `AIMessage` 和 `ToolMessage`，并将它们保存到 PostgreSQL，保证 Thread Detail
能够读取最终 Assistant 输出和本次工具调用结果。

本能力只负责 LangGraph Message 到 PostgreSQL `Message/ToolCall` 的持久化。
Run 终态仍遵循 [`RUN-LC-002`](../lifecycle/spec.md)，Redis/SSE 事件仍由
[`run/event-streaming`](../event-streaming/spec.md) 定义。

## 2. Scope

本次范围：

- 在 `server/service/thread_service.py` 增加
  `save_message_from_langgraph_state`、`save_ai_message` 和
  `save_tool_message`；
- 使用当前 Agent 实例和运行上下文构建相同的 LangGraph config，通过异步
  `aget_state` 读取 checkpoint；
- 只根据 LangChain Message 的 `type` 字段处理 `ai` 和 `tool`；
- AI Message 创建 Assistant Message，并保存该工具的 `id/name/args`；
- Tool Message 使用 `tool_call_id` 更新工具结果和 `success/error` 状态；
- 为 `AgentRun` 增加 `output_message_id`，指向本次 Run 最后保存的
  AI Message；
- `ConversationRepository` 按 Conversation -> Message -> ToolCall 聚合负责
  Message 和 ToolCall 持久化；
- 所有数据库创建、查询和更新由 Repository 的具体方法执行。

本次不包含：

- `tool_call_id` 缺失时按名称、位置或其他字段回退匹配；
- checkpoint 历史裁剪、重复同步或幂等扩展；
- 新的 `MessageRepository` 或 `ToolCallRepository`；
- Redis、SSE、前端或 Run 终态协议调整。

## 3. Current persistence ownership

### RUN-MP-001 Input and output association

`AgentRun.trigger_message_id` 标识触发当前 Run 的输入 Message；
`AgentRun.output_message_id` 标识当前 Run 的输出 Message。每个持久化
Assistant Message 仍通过 `Message.agent_run_id` 关联当前 Run。

一次 Run 可以产生发起工具调用和输出最终文本的两个 AI Message。
`save_ai_message` 返回创建的 Assistant Message；
`save_message_from_langgraph_state` 按 checkpoint 原始顺序遍历并持续覆盖
`saved_ai_message`。遍历结束后，只有当前 Run 和 `saved_ai_message` 都存在时，才将
最后一条 AI Message ID 写入 `AgentRun.output_message_id`，不需要额外的 sequence。

`ConversationRepository.get_run_result_message(run_id)` 必须通过
`AgentRun.output_message_id` 读取结果，不再按 `Message.agent_run_id` 猜测最新一条。

### RUN-MP-002 Repository ownership

- `ConversationRepository` 拥有 Assistant Message 创建、Run 结果查询、
  `add_tool_call` 和 `update_tool_call`；
- `AgentRunRepository` 拥有 `output_message_id` 的更新；
- Thread Service 只提取 LangChain 字段、调用 Repository 并控制一次事务；
- Repository 方法只 `flush`，`save_message_from_langgraph_state` 在全部消息处理完成后
  统一 `commit`。

该所有权与现有外键层级一致：

```text
Conversation
  -> Message      ON DELETE CASCADE
      -> ToolCall ON DELETE CASCADE
```

物理删除 Conversation 时，数据库先级联删除其 Message，再级联删除
Message 下的 ToolCall，不增加手工遍历删除逻辑。
`AgentRun.output_message_id` 对 `Message.id` 使用 `ON DELETE SET NULL`，避免
单独删除 Message 后留下无效指针。现有 `soft_delete_tree` 仍只软删除
Conversation；本能力不改变软删除行为。

## 4. Requirements

### RUN-MP-003 Read the LangGraph checkpoint

`save_message_from_langgraph_state` 使用当前 `BaseAgent` 实例创建具体 Context 和
`CompiledStateGraph`，通过显式 `run_id` 形参接收顶层 Run ID，并复用执行时的
LangGraph config：

```python
config = {
    "configurable": {
        "thread_id": context.thread_id,
        "uid": context.uid,
    }
}
checkpoint = await graph.aget_state(config)
messages = checkpoint.values.get("messages", [])
```

不得直接读取 checkpointer 表，也不得从 Redis Stream 反推最终 Message。

### RUN-MP-004 Dispatch by Message type

父方法只根据 `message.type` 分发：

- `ai` 调用 `save_ai_message`；
- `tool` 调用 `save_tool_message`；
- `human` 已由 Run 创建流程保存为 Trigger Message，本方法不重复保存；
- 其他类型不属于本次范围。

父方法按 `checkpoint.values["messages"]` 的原始顺序逐条处理。工具调用 AI Message
之后出现的 Tool Message 会在后续循环中自然进入 `tool` 分支，不增加额外的工具顺序
处理。保存 AI Message、查询 Run 和设置 output 都使用显式传入的 `run_id`，不从
Agent Context 读取。遍历结束后，父方法通过 `AgentRunRepository.get_by_id` 判断当前
Run 是否存在；仅当 Run 和最后保存的 AI Message 都存在时调用一次
`set_output_message`。

### RUN-MP-005 Save AI Message

`save_ai_message` 必须：

1. 使用 `message.text` 创建关联当前 Run 的 Assistant Message；
2. 返回新建的 Assistant Message，由父方法保留最后一次返回值；
3. 当 `message.tool_calls` 非空时，读取 `message.tool_calls[0]`；
4. 从该工具调用读取并保存原始 `id`、`name` 和 `args`；
5. `args` 只写入 `ToolCall.tool_arguments`，不重复写入 `tool_input`；
6. 不读取工具调用 content block 中重复出现的字段，不生成排序值。

最终 AI Message 的 `tool_calls` 为空时，只保存 Assistant Message。

### RUN-MP-006 Save Tool Message

`save_tool_message` 使用以下字段调用
`ConversationRepository.update_tool_call` 更新：

| Tool Message 字段 | PostgreSQL 字段 |
| --- | --- |
| `tool_call_id` | `ToolCall.tool_call_id` 查询条件 |
| `text` | `ToolCall.tool_result` |
| `status` | `ToolCall.status` |

更新查询只使用 `tool_call_id`。该字段按 LangGraph state 中的原始值保存和查询，即使
当前 Provider 返回空字符串也不增加 fallback。

`ToolCall.status` 只保存 LangChain `ToolMessage.status` 的 `success` 或 `error`；它不
是 `AgentRun.agent_status`，也不复用 `Message.status`。

### RUN-MP-007 ToolCall schema

`ToolCall` 不包含没有 LangGraph Message 来源的 `tool_sequence`，也不得用固定 `0`
或遍历位置替代。`ToolCall.status` 可空，创建 ToolCall 时保持为空，收到对应 Tool
Message 后写入实际结果状态。

`AgentRun.output_message_id` 是可空外键。由于 `Message.agent_run_id`
和 `AgentRun.output_message_id` 会在两张表之间形成两条关联路径，ORM 的
`AgentRun.messages` 和 `Message.agent_run` 必须明确指定
`Message.agent_run_id` 为 `foreign_keys`。

### RUN-MP-008 Completion ordering

`stream_agent_response` 的正常顺序必须是：

```text
Agent Stream 正常结束
  -> save_message_from_langgraph_state
  -> PostgreSQL commit
  -> yield finished
  -> Worker 持久化 completed 并发布 end
```

消息保存失败时不得发出 `finished`。异常继续传播给现有 Worker 失败处理，不增加新的
终态分支。

## 5. Acceptance Criteria

- 父方法通过 `aget_state` 读取 `checkpoint.values["messages"]` 并按 `type` 分发；
- Human Message 不会被重复保存；
- 工具调用 AI Message 创建一个 Assistant Message 和一个 ToolCall；
- ToolCall 保存 state 中原始的 `id/name/args`，没有排序字段；
- Tool Message 按 `tool_call_id` 更新 `tool_result/status`；
- ToolCall 创建和更新都由 `ConversationRepository` 执行；
- 最终 AI Message 创建最终 Assistant Message，并成为
  `AgentRun.output_message_id` 指向的 Message；
- Run 结果通过 `output_message_id` 读取；
- 保持 Conversation -> Message -> ToolCall 的物理删除级联；
- 消息事务提交完成后才允许产生 `finished`；
- 未增加 fallback、幂等、Redis、SSE 或前端行为。
