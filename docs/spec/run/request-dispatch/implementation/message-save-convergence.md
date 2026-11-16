# 实施切片：非正常消息 Save 收敛

## 1. 现状问题定位

目标：`server/service/thread_service.py`。

- 正常路径走 `save_message_from_langgraph_state`：读取 checkpoint 中的 `AIMessage`/`ToolMessage`，通过 `ModelMessageAuditRepository.reconcile_to_history` 转正流式审计行并回填 `ToolCall`。
- 异常/取消路径走 `save_partial_message`：跳过 checkpoint 与审计行 reconcile，直接新插 `role="assistant"` 消息。当多轮工具后在中途取消、或通过 `before_model` 跳 `END` 退出时，会导致已完成轮次未转正或审计行与部分消息并存；此外 `resume_agent_response` 的 `CancelledError` 分支未传 `full_msg`。

## 2. 收敛方案

1. **统一先同步已提交 Checkpoint**：
   - `stream_agent_response` 与 `resume_agent_response` 在 `before_model` 跳 `END` 正常退出流，以及在 `except asyncio.CancelledError` / `except Exception` 分支中，先使用独立 DB 会话调用 `save_message_from_langgraph_state`（持有 `lock_for_output_update` 校验 `worker_id`），将 checkpoint 中已完成的 `AIMessage` 与 `ToolMessage` 转正并更新 `ToolCall`。
2. **合并半截流式输出（仅硬取消/异常且存在未入 checkpoint 内容时）**：
   - 为 `resume_agent_response` 的 `CancelledError` 与 `Exception` 分支补齐 `full_msg = AIMessage(content="".join(accumulated_msg)) if accumulated_msg else None`。
   - `save_partial_message` 优先按当前轮 `model_audit` 的 `operation_id` 调用 `ModelMessageAuditRepository.reconcile_to_history` 将已流出的半截内容转为正式记录并附加 `is_error` / `error_type` / `stop_reason` 元数据；仅在未找到可转正的审计行时，才回退为新建截断消息并更新 `AgentRun.output_message_id`。
3. **Turn 边界 Steer 的元数据标识**：
   - 当 `before_model` 跳 `END` 退出且 checkpoint 最后一条消息是带 `tool_calls` 的 `AIMessage`（后面紧跟刚完成的 `ToolMessage`）时，不再额外生成空文本消息，在最后一条已保存 AI 消息的 `msg_metadata` 与 `AgentRun.run_metadata` 中记录 `stop_reason="steered"`，供前端区分“工具已执行完毕并转向下一条请求”。
