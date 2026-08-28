# Specification: Run Interrupt and Resume

## 1. Context and Scope

第一版用顶层 `LeaderAgent` 的单个 `ask_user(question: str, options: list[str])` 工具打通
可恢复的单选提问。工具调用 LangGraph `interrupt()` 后，当前 Run 结束为 `interrupted`；
用户提交所选 answer 时，后端创建新的 Resume Run，并从同一 Thread checkpoint 继续。

本能力不包含自由文本或表单回答、多选、多问题聚合、SubAgent 提问、超时和多人回答，也不接入
`HumanInTheLoopMiddleware` 或工具审批。取消仍按 [`cancellation`](../cancellation/spec.md)
执行，与可恢复打断保持独立。Resume 使用独立入口函数，但不复制 Agent 构造、事件适配或
checkpoint 保存循环。

## 2. State Model

```text
running --cancel--> cancel_requested -> cancelled
   |
   +--ask_user--> interrupted
                       |
                       +--resume--> pending -> running
                                               |-> completed
                                               |-> failed
                                               +-> interrupted
```

- `interrupted` 是当前 Run 的终态，父 Run 不再回到 `running`。
- Resume Run 使用新 `run_id`、`run_type="resume"` 和 `parent_run_id`。
- `parent_run_id` 指向被打断 Run；新 Run 继续使用同一 `thread_id` 和 checkpoint。
- 旧 Run ID 只用于父 Run 查询、校验、父子关联和刷新恢复，不重新入队，也不是
  LangGraph checkpoint key。

## 3. Contracts

### RUN-HIL-001 Interrupt metadata

Worker 把 LangGraph interrupt 规范化后写入父 Run 的 `run_metadata`：

```json
{
  "interrupt": {
    "kind": "ask_user",
    "question": "请选择继续执行所使用的数据库",
    "options": ["PostgreSQL", "MySQL"]
  }
}
```

第一版复用 `AgentRun.run_metadata`，不新增 Interaction 表或 checkpoint 字段。公开载荷
不得包含 checkpoint 内容，也不得推导默认答案或 ask_user 工具未返回的选项。

### RUN-HIL-002 Resume Run metadata

Resume Run 保存前端提交的 Run metadata：

```json
{
  "run_type": "resume",
  "parent_run_id": "<interrupted-run-id>",
  "run_metadata": {
    "resume": {
      "answer": "用户回答"
    }
  }
}
```

Resume Run 不创建 HumanMessage，`trigger_message_id` 为 `null`。`request_id` 是恢复请求的
幂等键；一个父 Run 至多创建一个 Resume 子 Run。

### RUN-HIL-003 Resume endpoint

```text
POST /api/agent/runs/{interrupted_run_id}/resume
```

```json
{
  "thread_id": "<thread-id>",
  "thread_metadata": {
    "request_id": "<client-idempotency-key>",
    "resume": {
      "answer": "请使用 PostgreSQL"
    }
  }
}
```

`AgentRunResumeRequest` 沿用 `AgentRunCreateRequest` 的 Run metadata 约定：恢复数据放在
`thread_metadata.resume`，幂等键放在 `thread_metadata.request_id`。Service 将
`thread_metadata` 复制到新 Resume Run 的 `run_metadata`；恢复请求不使用 `msg_metadata`。
成功响应返回新 Resume Run：

```json
{
  "run_id": "<resume-run-id>",
  "run_type": "resume",
  "parent_run_id": "<interrupted-run-id>",
  "thread_id": "<thread-id>",
  "status": "pending",
  "request_id": "<client-idempotency-key>",
  "stream_url": "/api/agent/runs/<resume-run-id>/events?thread_id=<thread-id>"
}
```

普通 `POST /api/agent/runs` 不承担恢复职责；未实现的 `is_resume` 和公开
`parent_run_id` 从普通创建请求中删除。

### RUN-HIL-004 Resume validation

创建 Resume Run 前，Service 必须在同一事务中锁定父 Run 并验证：

1. 父 Run 属于当前用户和请求 Thread；
2. 父 Run 状态为 `interrupted`；
3. `thread_metadata.resume.answer` 是父 Run `run_metadata.interrupt.options` 中的一个值；
4. 父 Run 尚无 Resume 子 Run；
5. 相同 `thread_metadata.request_id` 重试返回已有子 Run，其他重复恢复返回 `409`。

### RUN-HIL-005 Interrupt detection

LangGraph 在 `interrupt()` 暂停图时把打断信息写入 checkpoint。当前锁定的 LangGraph 1.2.9
中，`graph.aget_state(config)` 返回的 `StateSnapshot.interrupts` 直接包含 `Interrupt`；实现以
该字段为判断来源，不从 v3 stream event 的 values/params 推断打断。

`save_message_from_langgraph_state` 保持现有职责和 `None` 返回值，不承担打断检测。
打断检测封装为同文件内的异步 `check_agent_interrupt_handler`：函数根据当前
Agent context 获取 graph，调用 `graph.aget_state(config)`，读取 `state.interrupts`，并把
`Interrupt.value` 交给 `build_agent_interrupt_message`，按 ask_user 工具合同构造
`kind/question/options` payload。

第一版只接受单个 `ask_user` interrupt：无 interrupt 返回 `None`；单个合法 interrupt 返回
builder 构造的 payload；多个 interrupt、非字典 value、错误 kind、空 question 或空/非法
options 必须抛出明确异常，不得当作“未打断”继续发送 `finished`。builder 不生成 answer；
answer 只在 Resume 请求中出现。

普通或 Resume graph stream 结束后，对应 Thread Service 入口必须先保存 checkpoint 消息，
再调用该函数。普通入口使用其内部的 `make_agent_stream_event`，Resume 入口使用其内部的
`make_agent_resume_event`；两个 builder 不共享，只保持相同的 bytes 字段合同：

```python
await save_message_from_langgraph_state(...)
interrupt_payload = await check_agent_interrupt_handler(
    agent_instance=agent_instance,
    context=agent_context,
)
if interrupt_payload is not None:
    # Resume 入口在相同位置调用 make_agent_resume_event。
    yield make_agent_stream_event(
        status="interrupted",
        interrupt=interrupt_payload,
    )
    return
```

该 bytes chunk 经既有 `_cancellable_stream` 进入 `process_agent_run`，再由
`_normalize_steam_agent_chunk` 解码为事件字典。只有 Worker 解释 `status="interrupted"`
并执行运行状态收敛；`stream_agent_response` 不发送 `finished`，也不写 Run 状态、
`interaction_required` 或 `end`。Thread Service 在 yield interrupted chunk 后返回；Worker
循环内只按每个 chunk 的 `status` 处理，不使用 `terminal_flag` 判断是否继续处理，也不使用
`break`、`continue` 或立即 `return` 控制消费循环，而是在状态收敛后等待该 stream 自然耗尽。

参考：[LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)、
[LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)。

`stream_agent_response` 只处理普通消息输入，不根据 `run_type` 选择 Resume 输入，也不从
metadata 中提取 answer。Resume 由同级 `resume_agent_response` 和 BaseAgent 专用
`stream_message_by_resume` 承载。

### RUN-HIL-006 Unified finalization and publish ownership

Worker 的 `process_agent_run` 必须以解码后的 chunk `status` 驱动控制操作。过程状态继续
转发或缓冲；Thread Service 只使用 `finished`、`error` 和 `interrupted` 三种停止信号并统一调用
`_finalize_run`，不得为 interrupt 保留 `_finalize_interrupted_run`，也不得在对应 case 中
用 `break` 或立即 `return` 截断 stream。

`_finalize_run` 是 Worker 统一的数据库状态转换入口，并返回 PostgreSQL 中的实际
`(agent_status, changed)`：

- `finished` 请求转换为 `completed`；
- `error` 请求转换为 `failed`，并保存 `error/error_type`；
- `cancelled` 请求转换为 `cancelled`；
- `interrupted` 请求转换为 `interrupted`，并复用现有 `error/error_type` 保存打断消息和 kind。

`_finalize_run` 统一执行数据库状态转换和终态事件发布，并返回
`(agent_status, changed)`。只有 `changed=True` 时发布：普通
`completed/failed/cancelled` 发布 `end`；`interrupted` 依次发布
`interaction_required` 和 `end(status=interrupted)`。

父 Run 的 `finished/error/interrupted` case 在 `_finalize_run` 返回后继续处理同一次结果：

- `changed=True` 时，当前 case 再调用一次 `write_end_stream_event`；payload 顶层
  `status` 使用实际 `agent_status`，`chunk` 保存当前 Thread Service 原始停止消息；
- `changed=False` 时，当前 case 不二次发布；
- `_finalize_run` 的现有发布与 case 的二次发布同时保留，不去重。

`error` 只属于 Thread Service 到 Worker 的内部 chunk 合同；PostgreSQL 中的 Run 终态和对外
`end` 事件仍使用 `failed`。Thread Service 不生成 `status="failed"`，Worker 也不保留
`error/failed` 双分支兼容。

Repository 层使用同一个 `set_agent_terminal` 处理
`completed/failed/cancelled/interrupted`。打断内容序列化到现有 `error`，`kind` 使用现有
`error_type`，Repository 同步构造 `run_metadata.interrupt`；不增加 `set_interrupted`、
`set_run_interrupted` 或 `interrupt_payload` 专用参数。

每个停止状态 case 在 `_finalize_run` 返回后按同一规则处理：

1. 先调用 `_finalize_run` 取得实际 `(agent_status, changed)`；
2. `changed=True` 时，在当前 case 内二次发布
   `end({"status": agent_status, "chunk": current_chunk})`；
3. `changed=False` 时不二次发布；
4. 每个 case 最后都在内部执行
   `terminal_flag = agent_status in AGENT_RUN_TERMINAL_STATUSES`，该判断与 `changed` 无关；
5. case 不读取 `terminal_flag`，也不使用 `break`、`continue` 或立即 `return`；等待 Thread
   Service stream 自然耗尽并退出数据库上下文后，flag 为真则裸返回；否则先由
   `AgentRunContext` 判断是否取消，取消时
   调用 `_finalize_run(status="cancelled")`，否则按流协议错误调用
   `_finalize_run(status="failed")`。

只有正式 `finished` chunk 能把 Run 转换为 `completed`。stream 在没有任何停止状态的情况
下耗尽属于流协议错误，必须收敛为 `failed`，不得沿用默认 completed 兜底。PostgreSQL 已
提交但 Redis 发布失败时仍以数据库状态为事实来源。

### RUN-HIL-007 Resume execution

Resume Service 只把新 Resume Run ID 入队。Worker 必须先根据持久化的
`run_type="resume"` 选择恢复分支，再决定是否读取普通 `trigger_message_id`；不得根据
metadata 中是否存在 `interrupt` 猜测运行类型。

Worker 把新 Run 的 `run_metadata` 加入 `runtime_metadata`。恢复分支调用与
`stream_agent_response` 同在 `server/service/thread_service.py` 的
`resume_agent_response`；该函数只校验/提取当前回答并构造：

```python
Command(resume=runtime_metadata["resume"]["answer"])
```

随后 `resume_agent_response` 把该 Command 交给
`BaseAgent.stream_message_by_resume`，不再调用 `stream_agent_response`。
`stream_message_by_resume` 与 `stream_messages_with_event` 使用相同 Agent context、
configurable config 和 v3 event 输出合同，但只接受 `Command(resume=...)`，不得包装为
`{"messages": ...}`，也不得创建或重放 HumanMessage。

两个 Thread Service 入口分别消费普通流和 Resume 流，但继续使用相同的 chunk 构造、
checkpoint 消息保存和 `check_agent_interrupt_handler` 合同；不得为 Resume 建立另一套
持久化或 Worker 事件协议。

恢复继续使用父 Run 的 `thread_id` 和当前用户 UID 构造相同 configurable config，不再
传入父 HumanMessage。Checkpoint 缺失时 Resume Run 写为 `failed`，不得重放父输入。

### RUN-HIL-008 Message persistence

中断前保存 `ask_user` AI Tool Call；恢复后保存包含用户回答、且关联原
`tool_call_id` 的 ToolMessage，再保存后续 AI 输出。Checkpoint 重读不得重复插入历史
AIMessage、ToolMessage 或 ToolCall。

### RUN-HIL-009 Interaction event

```json
{
  "event_type": "interaction_required",
  "payload": {
    "kind": "ask_user",
    "parent_run_id": "<interrupted-run-id>",
    "question": "请选择继续执行所使用的数据库",
    "options": ["PostgreSQL", "MySQL"]
  }
}
```

该事件后发送 `end(status=interrupted)`，关闭父 Run Stream。Redis Stream 只传输事件，
PostgreSQL 继续拥有 Run 状态和 interrupt metadata。

### RUN-HIL-010 Frontend ownership

`useAgentRun` 保存 `pendingInteraction`，提交
`resumeRun(parentRunId, request)`，其中请求按上述 `thread_metadata` 结构构造；成功后切换到
响应中的新 Run ID 和 Stream URL。
`ChatView` 组合 `ChatAskUserComponent`；问题、选项和回答不伪造成普通聊天消息，也不写入
`localStorage`。现有 `ChatHumanaApproveComponent` 本轮不接线。

### RUN-HIL-011 Refresh recovery

`ThreadDetailResponse` 返回后端计算的：

```ts
active_run: ThreadRunMetadataResponse | null
pending_interaction: InteractionRequired | null
```

`pending_interaction` 是尚无 Resume 子 Run 的最新 interrupted Run。存在待回答问题时，
前后端都阻止普通消息提交。

## 4. Failure Contract

- 父 Run 不存在或不属于当前用户：`404`；
- 状态或 Thread 不匹配：`409`；
- `thread_metadata.resume` 无效，或 answer 不在父 Run 的 options 中：`422`；
- 不同 `thread_metadata.request_id` 重复恢复同一父 Run：`409`；
- Redis 发布失败：PostgreSQL 状态和 metadata 保持有效，读取侧按数据库收敛；
- Resume Run 执行中取消：沿用现有 `cancel_requested -> cancelled`。

## 5. Acceptance Criteria

- `ask_user -> interrupted -> resume -> ToolMessage -> AI` 端到端可用；
- 父 Run 保持 `interrupted`，只有新 Resume Run ID 被入队和监听；
- `run_type` 决定普通或恢复分支，`run_metadata` 只承载本次运行数据；
- `resume_agent_response` 准备 Resume Command 并调用 `stream_message_by_resume`，不委托
  `stream_agent_response`；
  `check_agent_interrupt_handler` 独立获取 state，并通过 `build_agent_interrupt_message`
  构造 question/options；
  普通入口内部使用 `make_agent_stream_event`，Resume 入口内部使用
  `make_agent_resume_event`，两者 yield 相同字段合同的 interrupted chunk；
  `process_agent_run` 按 chunk status 调用统一 `_finalize_run`，并等待 stream 自然耗尽；
- `_finalize_interrupted_run`、`set_run_interrupted` 和 Repository `set_interrupted` 均不存在；
  interrupted 与其他终态共用 `set_run_terminal -> set_agent_terminal`；
- `_finalize_run` 保留现有 changed-only 发布；`changed=True` 时当前 case 再发布携带原始
  chunk 的 `end`，`changed=False` 时不二次发布；
- `error/finished/interrupted` 分别在 case 内根据实际 `agent_status` 设置 `terminal_flag`；
- 只有显式 `finished` chunk 能收敛为 completed，无停止状态的流耗尽收敛为 failed；
- Thread Service 内部只发送 `error`，Worker 将其映射为 PostgreSQL 和 `end` 事件的 `failed`；
- 重复恢复、越权、错误 Thread 和缺失 checkpoint 均有确定结果；
- 刷新后能恢复活动 Resume Run 或待回答问题；取消与打断互不复用状态和信号。
