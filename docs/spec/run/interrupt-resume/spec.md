# Specification: Run Interrupt and Resume

## 1. Context and Scope

顶层 `LeaderAgent` 的工具参数采用 `ask_user(questions: list[HumanQuestion])`：一次工具
调用包含多个独立的单选问题，通过一次 LangGraph `interrupt()` 暂停并等待回答。

当前目标覆盖多问题展示、回答提交、Resume Run 创建、Worker 传参以及恢复流的完整收尾。
本文定义能力目标与既有设计边界，不表示生产代码已经完成适配。
已有工具、解析、handler、消息保存和终态函数作为现有依赖，保持实现与签名。
当前实施只补齐恢复入口及前后端调用处的参数与事件接线，范围见根目录 plan.md。

本次不包含自由文本、多选、多个并行工具中断的业务处理、SubAgent 提问、超时和多人回答，
也不接入 `HumanInTheLoopMiddleware` 或工具审批。取消仍按
[`cancellation`](../cancellation/spec.md) 执行，与可恢复打断保持独立。

### 工具参数与原生中断载荷

`src/agents/leaderagent/tools.py` 拥有 `QuestionOption`、`HumanQuestion` 和 `ask_user`：

- `QuestionOption` 包含 `label: str`（展示文字）与 `value: str`（回答值）。
- `HumanQuestion` 包含 `question_id: str`、`question: str` 与
  `options: list[QuestionOption]`；问题标识、问题文字和选项由模型生成。
- Pydantic 类型与 `Field(description=...)` 生成模型可见的嵌套工具 Schema。
  问题标识唯一性是描述约定，解析函数不检查内部字段或集合唯一性。
- `ask_user` 将每个问题 `model_dump()` 后写入一次中断，不自行生成问题、选项或默认答案。

原生 `Interrupt.value` 示例：

```json
{
  "kind": "ask_user",
  "questions": [
    {
      "question_id": "database",
      "question": "请选择数据库",
      "options": [{"label": "PostgreSQL", "value": "postgresql"}]
    },
    {
      "question_id": "environment",
      "question": "请选择部署环境",
      "options": [{"label": "本地部署", "value": "local"}]
    }
  ]
}
```

调用方应以 `{"database": "postgresql", "environment": "local"}` 这样的
`question_id -> option.value` 字典恢复中断。工具原样返回恢复值，不再调用 `str()`；
回答字段及选项合法性由 Run Service 在创建恢复 Run 前验证。

工具级证据由 `test/test_ask_user_tool.py` 验证：模型 Schema 包含嵌套字段说明；真实内存
checkpoint 中只有一个 interrupt，包含两道完整问题；按 ID 恢复后，原工具调用的
ToolMessage 保留两道问题各自的答案。

### 问题载荷解析

`server/utils/interrupt_utils.py` 提供普通函数 `parse_interrupt_questions(questions)`：
列表原样返回，单个问题字典包装为列表，其他类型抛出 `ValueError`。
这里的字典是包含 `question_id`、`question`、`options` 的单个问题，不是整个 Interrupt.value。
函数只统一外层结构，不检查内部字段、选项、空集合或重复标识，也不修改原始内容。
函数由 Thread Service 的 AskHuman 构建函数调用。
`test/test_interrupt_utils.py` 覆盖列表直返、单问题多选项包装与不支持的输入类型。

### 服务端 AskHuman 实体

`server/utils/interrupt_utils.py` 中的 `AskHumanPayload` 使用普通 dataclass，包含
`thread_id`、`run_id`、`questions` 和默认值为 `ask_user` 的 `kind`，不增加字段验证。
`thread_id` 表示所属会话，`run_id` 表示产生中断的执行；恢复时新 Run 的
`parent_run_id` 指向该 Run，同一会话可以经历多次 Run 和中断。
`build_agent_interrupt_message` 将实体转换为字典供事件链路使用。
实时中断入口传入 context 的 thread_id/run_id；线程详情重建待回答问题时传入持久化 Run 的
thread_id/id，并保留 parent_run_id。实时事件和刷新恢复使用相同 questions 结构。

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
    "questions": [{"question_id": "database", "question": "请选择数据库", "options": [{"label": "PostgreSQL", "value": "postgresql"}]}]
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
      "answers": {"database": "postgresql"}
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
      "answers": {"database": "postgresql"}
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
3. `thread_metadata.resume.answers` 是非空的 `question_id -> option.value` 字典；键集合必须与父 Run 的 questions 完全一致，每个值必须属于对应问题的 options；问题 ID 重复或问题结构无效时拒绝恢复；
4. 父 Run 尚无 Resume 子 Run；
5. 相同 `thread_metadata.request_id` 且 answers 相同的重试返回已有子 Run；相同键不同回答或其他重复恢复返回 `409`。

### RUN-HIL-005 Interrupt detection

LangGraph 在 `interrupt()` 暂停图时把打断信息写入 checkpoint。沿用现有调用链：

```text
check_agent_interrupt_handler
  -> graph.aget_state(config)
  -> _reslove_agent_interrupt
  -> build_agent_interrupt_message
  -> chunk_iterator
```

`check_agent_interrupt_handler` 保持异步生成器，接收 `agent_instance`、
`runtime_metadata`、`chunk_iterator` 和 `context`，产出 bytes chunk。
`_reslove_agent_interrupt` 现从 checkpoint 的 tasks 中提取首个中断；本轮不替换读取路径。
`build_agent_interrupt_message` 保留现有格式化、实体构建及字典转换职责；
handler 将其 `status` 交给调用方提供的 builder，并传入 `pending_interrupt` 和
`runtime_metadata`。调用方使用 `async for` 消费，不能把该生成器当作返回 payload 的协程。

`save_message_from_langgraph_state` 保持现有职责和 `None` 返回值，不承担打断检测。
普通入口与恢复入口分别使用自己的 chunk builder，复用现有检测与保存函数。
问题字段及回答校验仍按 RUN-HIL-004 归 Run Service，不向解析函数或 dataclass 增加验证。

中断事件最终由 Worker 收敛 Run 状态并发布 RUN-HIL-009 的交互事件。
Worker 按 handler 已有的 `ask_human/pending_interrupt` 读取中断问题，调用
`_finalize_run(status="interrupted", payload=...)`。普通入口保留中断标志和状态解析，但先暂存
handler 生成的中断 chunk；checkpoint 消息保存成功后才向 Worker 发出该 chunk 并返回。
恢复入口同样先保存再消费中断 chunk。两个入口均不在中断后发送 finished；保存失败时只发出
error，不得先把 Run 收口为 interrupted。handler 和终态函数保持现有实现。

`stream_agent_response` 只处理普通消息输入，不根据 `run_type` 选择 Resume 输入，也不从
metadata 中提取 answer。Resume 由同级 `resume_agent_response` 和 BaseAgent 专用
`stream_message_by_resume` 承载。

### RUN-HIL-006 Unified finalization and publish ownership

Worker 的 `process_agent_run` 必须以解码后的 chunk `status` 驱动控制操作。过程状态继续
转发或缓冲；Thread Service 使用 `finished`、`error` 和 `ask_human` 三种停止信号，Worker 统一调用
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

父 Run 的 `finished/error/ask_human` case 在 `_finalize_run` 返回后继续处理同一次结果：

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
`resume_agent_response`；Worker 从持久化的 `run_metadata.resume.answers` 提取
`resume_input`，显式传给恢复入口。恢复入口构造：

```python
Command(resume=resume_input)
```

随后 `resume_agent_response` 把该 Command 交给
`BaseAgent.stream_message_by_resume`，不再调用 `stream_agent_response`。
恢复入口显式接收 resume_input、thread_id、runtime_metadata、current_user 和 db，不接收 agent_slug。
当前中断只发生在主 Agent；恢复入口通过 `agent_manager.get_agent("LeaderAgent")` 获取主 Agent，
不按 slug 选择执行实例。父 Run 的 agent_id 仍用于持久化关联。
resume_input 是已校验的回答字典；runtime_metadata 承载运行身份与配置，入口不再从中提取回答。
模型配置沿用父 Run 的 model（若未指定则保持既有默认解析规则），前端回答不能更换 Agent 或模型。
恢复入口仍负责运行上下文、会话校验、流事件转换、累计输出、消息保存、再次中断检测和异常处理。
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
    "questions": [{"question_id": "database", "question": "请选择数据库", "options": [{"label": "PostgreSQL", "value": "postgresql"}]}]
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
组件按 questions 展示每道题并收集 answers，全部作答后一次提交；选项展示 label、提交 value。
这是一份 interrupt 的多个问题答案，不是 LangGraph 多个 interrupt ID 的恢复映射。

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
- `thread_metadata.resume.answers` 无效、漏答、多余问题或值不在对应 options 中：`422`；
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
  构造 questions；
  普通入口内部使用 `make_agent_stream_event`，Resume 入口内部使用
  `make_agent_resume_event`，按现有异步生成器合同消费中断；内部事件接通后由 Worker 收敛为 interrupted；
  `process_agent_run` 按 chunk status 调用统一 `_finalize_run`，并等待 stream 自然耗尽；
- `_finalize_interrupted_run`、`set_run_interrupted` 和 Repository `set_interrupted` 均不存在；
  interrupted 与其他终态共用 `set_run_terminal -> set_agent_terminal`；
- `_finalize_run` 保留现有 changed-only 发布；`changed=True` 时当前 case 再发布携带原始
  chunk 的 `end`，`changed=False` 时不二次发布；
- `error/finished/ask_human` 分别在 case 内根据实际 `agent_status` 设置 `terminal_flag`；
- 只有显式 `finished` chunk 能收敛为 completed，无停止状态的流耗尽收敛为 failed；
- Thread Service 内部只发送 `error`，Worker 将其映射为 PostgreSQL 和 `end` 事件的 `failed`；
- 重复恢复、越权、错误 Thread 和缺失 checkpoint 均有确定结果；
- 刷新后能恢复活动 Resume Run 或待回答问题；取消与打断互不复用状态和信号。
