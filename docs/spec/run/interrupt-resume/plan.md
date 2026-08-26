# Implementation Plan: Run Interrupt and Resume

计划版本：`v0.1.0`

## 1. Implementation Order

1. 用最小 `ask_user` fixture 固定当前 LangGraph interrupt/resume 真实结构。
2. 实现 `interrupted` 持久化、父子 Resume Run 查询和恢复幂等约束。
3. 增加专用 Resume API：旧 Run ID 定位父 Run，`thread_metadata.resume` 承载回答，后端生成
   并入队新 Run ID。
4. 让 Worker 在读取普通输入前按 `run_type` 选择 `stream_agent_response` 或同级的
   `resume_agent_response`；后者构造 `Command(resume=answer)` 并调用 BaseAgent 专用
   `stream_message_by_resume`。
5. 接入 `ask_user`、interaction/end 事件和消息幂等保存。
6. 接入前端提问组件、Resume Stream 切换和 Thread 刷新恢复。
7. 完成后端定向测试、前端检查和静态验证。

## 2. File Changes

### 2.1 Runtime fixture

- `test/test_agent_run_interrupt_resume.py`
  - 测试内定义 `ask_user(question: str, options: list[str])`；
  - 首次运行断言 `Interrupt.value` 和 `__interrupt__`；
  - `Command(resume="用户回答")` 后断言 ToolMessage 关联原 Tool Call，模型继续输出。

该 fixture 决定属性访问方式；实现不增加多版本兼容 parser。

### 2.2 Run persistence

- `src/database/models.py:AgentRun`
  - 状态说明加入 `interrupted`，运行类型说明加入 `resume`；
  - `trigger_message_id` 允许 Resume Run 为 `null`，不新增表或 JSON 列。
- `src/database/repositories/agent_run_repository.py`
  - active 查询把 `interrupted` 视为已结束；
  - 新增 `set_interrupted(run_id, payload)`；
  - 新增带父行锁的 Resume 子 Run 查询；
  - `set_agent_terminal` 保持 `completed/failed/cancelled`，不接收 interrupt payload。

目标：`AgentRunRepository.set_interrupted`

```python
run = await self._lock_update(run_id)
if run is None or str(run.agent_status) in AGENT_RUN_TERMINAL_STATUSES | {
    "interrupted"
}:
    return run, False

run.run_metadata = {**dict(run.run_metadata or {}), "interrupt": payload}
run.agent_status = "interrupted"
run.finished_at = datetime.now(UTC)
await self.session.flush()
return run, True
```

### 2.3 Resume API and Service

- `server/entities/agent.py`
  - 新增 `AgentRunResumeRequest(thread_id, thread_metadata)`；`thread_metadata` 与
    `AgentRunCreateRequest` 一样使用 `Field(default_factory=dict)`；
  - 校验 `thread_metadata.resume.answer` 为非空字符串；
  - 从普通 `AgentRunCreateRequest` 删除 `is_resume` 和公开 `parent_run_id`。
  - Resume DTO 当前单独保留以便明确入口和测试，不增加共享基类或兼容层。
- `server/router/agent_router.py`
  - 新增 `POST /runs/{interrupted_run_id}/resume`；
  - Router 只负责鉴权、DTO 和 `404/409/422` 映射。
- `server/service/agent_run_service.py:create_resume_agent_run_service`
  - 锁定并校验旧父 Run；
  - 校验 answer 属于父 Run `run_metadata.interrupt.options`；
  - 相同 `request_id` 返回已有子 Run，不同请求重复恢复返回冲突；
  - 生成新 Run ID，保存 `run_type="resume"`、父 Run ID 和请求 `thread_metadata`；
  - 不创建 Message，提交后只入队新 Run ID。

```python
parent = await run_repo.get_for_resume_for_update(
    run_id=interrupted_run_id,
    uid=current_user.uid,
    thread_id=request.thread_id,
)
run_metadata = dict(request.thread_metadata)
resume = run_metadata["resume"]
request_id = str(run_metadata.get("request_id") or uuid.uuid4())
validate_resume(parent, resume)

existing = await run_repo.get_resume_child(interrupted_run_id)
if existing is not None:
    if str(existing.request_id) == request_id:
        return existing
    raise AgentRunConflict("当前问题已回答")

resume_run = await run_repo.create_run(
    run_id=str(uuid.uuid4()),
    thread_id=str(parent.thread_id),
    conversation_id=int(parent.conversation_id),
    uid=str(parent.uid),
    agent_slug=str(parent.agent_id),
    request_id=request_id,
    trigger_message_id=None,
    run_type="resume",
    parent_run_id=str(parent.id),
    run_metadata=run_metadata,
)
await db.commit()
await enqueue_agent_run(str(resume_run.id))
```

### 2.4 Agent stream and Resume separation

- `src/agents/base_agent.py:stream_messages_with_event`
  - 继续只接收普通 messages，并使用 `input={"messages": messages}`；
  - 继续按当前合同转发 v3 event，不增加 interrupt 解析或 state 查询，也不拥有 Run 状态。
- `src/agents/base_agent.py:stream_message_by_resume`
  - 新增 Resume 专用方法，只接收 `Command(resume=answer)` 和 `runtime_context`；
  - 与 `stream_messages_with_event` 一样构造 Agent context、graph 和包含 `thread_id/uid` 的
    configurable config；
  - 调用 `agent.astream_events(input=resume_command, version="v3", ...)`，不包装
    `{"messages": ...}`，不创建或重放 HumanMessage；
  - 对外 yield 与普通方法相同的 method/payload 合同，使 Thread Service 后续处理保持一致；
  - 不解析 interrupt，不写数据库，也不拥有 Run 状态。
- `server/service/thread_service.py:stream_agent_response`
  - 只接收普通 message 输入并调用 `stream_messages_with_event`；
  - 负责 Agent 构造、v3 事件观察和 checkpoint 消息保存；
  - graph stream 结束并保存 checkpoint 消息后，调用
    `check_agent_interrupt_handler`；
  - 不从 values event 或 `params.interrupts` 判断打断；
  - 在函数内部保留 `make_agent_stream_event`；解析函数返回 payload 时由它构造
    `status="interrupted"` chunk 并 yield 给 Worker；
  - yield 后立即 return，不修改 Run 状态，也不发布 Redis 生命周期事件；
  - 执行异常通过自己的 builder 构造 `status="error"`、`error` 和 `error_type` chunk，
    由 Worker 统一决定 failed 状态和停止事件。
- `stream_agent_response.<locals>.make_agent_stream_event` 与
  `resume_agent_response.<locals>.make_agent_resume_event`
  - 两个 builder 分别封装在所属入口内部，不提升为模块函数，也不相互调用；
  - 两者保持相同的 bytes 字段合同，公共事件消费逻辑通过当前入口传入的 builder 构造 chunk。
- `server/service/thread_service.py:check_agent_interrupt_handler`
  - 异步函数，根据 `agent_instance` 和当前 context 获取 graph；
  - 使用当前 `thread_id`、`uid` 构造 config 并调用 `graph.aget_state(config)`；
  - 只读取返回的 `StateSnapshot.interrupts`；
  - 当前 LangGraph 1.2.9 定向 fixture 必须确认该字段包含暂停产生的 `Interrupt.value`；
  - 无 interrupt 时返回 `None`；单个 interrupt 交给 `build_agent_interrupt_message`；
  - 多个 interrupt 抛出明确异常，防止误报完成；
  - 不访问业务数据库、Redis，也不生成 stream chunk。
- `server/service/thread_service.py:build_agent_interrupt_message`
  - 根据 ask_user 工具的 `Interrupt.value` 构造 `kind/question/options`；
  - question 必须为非空字符串，options 必须为非空字符串列表；
  - 不生成 answer，不访问 graph、数据库或 Redis。
- `server/service/thread_service.py:resume_agent_response`
  - 与 `stream_agent_response` 同级，替换当前空的 `stream_resume_response`；
  - 从 `runtime_metadata.resume.answer` 构造 `Command(resume=answer)`；
  - 把 Command 和原 Thread/UID context 交给 `agent_instance.stream_message_by_resume`，不再
    调用 `stream_agent_response`；
  - 在函数内部定义并只使用 `make_agent_resume_event`；
  - 消费 Resume v3 events 后，沿用相同 chunk、checkpoint 消息保存和 interrupt 检测合同；
  - 执行异常通过自己的 builder 构造与普通入口相同字段合同的 `status="error"` chunk；
  - 不把 Resume answer 转成普通 Message。

```python
async def resume_agent_response(*, runtime_metadata, **stream_kwargs):
    answer = runtime_metadata["resume"]["answer"]
    async for method, payload in agent_instance.stream_message_by_resume(
        Command(resume=answer),
        runtime_context=agent_runtime_context,
    ):
        # 按相同字段合同调用当前入口内部的 make_agent_resume_event。
        ...


# BaseAgent
async def stream_message_by_resume(
    self,
    resume_command: Command,
    runtime_context=None,
    **kwargs,
):
    context = self.agent_context()
    context.update_context(runtime_context or {})
    agent = await self.get_agent(context)
    input_config = {
        "configurable": {
            "thread_id": context.thread_id,
            "uid": context.uid,
        }
    }
    async with await agent.astream_events(
        input=resume_command,
        config=input_config,
        version="v3",
        context=context,
        **kwargs,
    ) as stream_events:
        async for stream_event in stream_events:
            # 沿用 stream_messages_with_event 当前的 method/payload 输出合同。
            ...


async def check_agent_interrupt_handler(
    *, agent_instance: BaseAgent, context: BaseContext
) -> dict[str, Any] | None:
    graph = await agent_instance.get_agent(context)
    state = await graph.aget_state(
        {
            "configurable": {
                "thread_id": context.thread_id,
                "uid": context.uid,
            }
        }
    )
    interrupts = state.interrupts
    if not interrupts:
        return None

    if len(interrupts) != 1:
        raise ValueError("Only one ask_user interrupt is supported")

    return build_agent_interrupt_message(interrupts[0])


def build_agent_interrupt_message(interrupt: Interrupt) -> dict[str, Any]:
    value = interrupt.value
    if (
        not isinstance(value, dict)
        or value.get("kind") != "ask_user"
        or not isinstance(value.get("question"), str)
        or not value["question"].strip()
        or not isinstance(value.get("options"), list)
        or not value["options"]
        or not all(
            isinstance(option, str) and option.strip()
            for option in value["options"]
        )
    ):
        raise ValueError("Invalid ask_user interrupt payload")

    return {
        "kind": "ask_user",
        "question": value["question"],
        "options": list(value["options"]),
    }


# stream_agent_response：graph stream 结束后
await save_message_from_langgraph_state(...)
interrupt_payload = await check_agent_interrupt_handler(
    agent_instance=agent_instance,
    context=agent_runtime_context,
)
if interrupt_payload is not None:
    yield make_agent_stream_event(
        status="interrupted",
        interrupt=interrupt_payload,
    )
    return
```

目标文件与函数：`src/agents/base_agent.py:stream_message_by_resume`、
`server/service/thread_service.py:resume_agent_response`、
`server/service/thread_service.py:stream_agent_response`、
`server/service/thread_service.py:check_agent_interrupt_handler`、
`server/service/thread_service.py:build_agent_interrupt_message`。普通输入由 Worker
转换为 graph message 输入；Resume answer 只进入 `Command(resume=...)`。第一版不增加
detector 类或新模块；BaseAgent 两个入口保持相同输出合同，但职责不合并。

### 2.5 Worker lifecycle

- `server/worker.py:_finalize_run`
  - 作为普通、错误、取消和打断的统一数据库状态转换入口；删除
    `_finalize_interrupted_run`；
  - `status="interrupted"` 时调用独立 `set_run_interrupted` 保存 payload，其余停止状态
    调用 `set_run_terminal`；本轮不合并两个 Repository 方法；
  - 只返回 PostgreSQL 实际 `(agent_status, changed)`，不写 Redis Stream。
- `server/worker.py:process_agent_run`
  - 先读取 `run_type`；普通 Run 构造 message 输入并调用 `stream_agent_response`，Resume
    Run 不查询 `trigger_message_id`，直接调用 `resume_agent_response`；
  - 把 `AgentRun.run_metadata` 合入 `runtime_metadata`；
  - 两个入口返回相同 chunk 合同，后续事件消费不按运行类型分叉；
  - 通过既有 `_cancellable_stream` 消费 bytes chunk，并使用 `_normalize_steam_agent_chunk`
    解码两个入口各自 builder 的结果；
  - 以 chunk `status` 作为控制入口：`finished` 收敛为 completed，`error/failed` 收敛为
    failed，`interrupted` 收敛为 interrupted；取消路径也调用同一个 `_finalize_run`；
  - 每个停止 case 都检查 `_finalize_run` 返回的实际 `agent_status` 是否属于停止状态，并
    保存 `terminal_result`；不为 `None` 或非停止状态增加额外异常；
  - 仅当 `changed=True` 时发布本次状态转换对应的停止事件；`changed=False` 不重复发布；
  - interrupted 的本次转换依次发布 interaction/end，其他停止状态发布 end；
  - 停止 case 使用 `continue`，不使用 `break` 或立即 `return`；Thread Service 在终止
    chunk 后自行返回，Worker 等待 stream 自然耗尽后再返回 `terminal_result`；
  - 只有显式 `finished` chunk 能写 completed；没有停止 status 的流耗尽按协议错误写
    failed，不保留 completed 兜底。
- `server/service/arq_queue_servcie.py`
  - 复用现有 Stream writer，不新增 Redis key、channel 或 sequence。

```python
if run_type == "resume":
    agent_stream = resume_agent_response(
        runtime_metadata=runtime_metadata,
        ...
    )
else:
    agent_stream = stream_agent_response(
        thread_input_message=agent_input_message,
        runtime_metadata=runtime_metadata,
        ...
    )

# FIXEME: 所有停止状态统一经过 _finalize_run，事件发布权由 changed 决定。
async for stream_chunk in _cancellable_stream(agent_stream, ...):
    for chunk in _normalize_steam_agent_chunk(stream_chunk):
        status = chunk.get("status")

        if terminal_result is not None:
            continue

        if status == "interrupted":
            await smoother.release()
            agent_status, changed = await _finalize_run(
                run_id,
                status="interrupted",
                interrupt_payload=chunk["interrupt"],
            )
            if agent_status in RUN_TERMINAL_STATUSES:
                terminal_result = (agent_status, changed)
                if changed:
                    await write_stream_event(
                        run_id, "interaction_required", payload, thread_id
                    )
                    await write_end_stream_event(
                        run_id, {"status": agent_status}, thread_id
                    )
            continue

        if status in {"error", "failed"}:
            agent_status, changed = await _finalize_run(
                run_id,
                status="failed",
                error=chunk.get("error"),
                error_type=chunk.get("error_type"),
            )
            if agent_status in RUN_TERMINAL_STATUSES:
                terminal_result = (agent_status, changed)
                if changed:
                    await write_end_stream_event(
                        run_id,
                        {"status": agent_status, "error": chunk.get("error")},
                        thread_id,
                    )
            continue

        if status == "finished":
            agent_status, changed = await _finalize_run(
                run_id,
                status="completed",
            )
            if agent_status in RUN_TERMINAL_STATUSES:
                terminal_result = (agent_status, changed)
                if changed:
                    await write_end_stream_event(
                        run_id, {"status": agent_status}, thread_id
                    )
            continue

if terminal_result is not None:
    return terminal_result
```

目标文件与函数：`server/worker.py:_finalize_run`、`server/worker.py:process_agent_run`。
第一版保留 status 分支内联，不新增独立 interrupt processor、终止 dispatcher 文件或只有
一个调用方的处理类。

### 2.6 Tool and message persistence

- `src/agents/leaderagent/tools.py:ask_user`
  - 同步 LangChain tool，输入为 `question: str` 和非空 `options: list[str]`；
  - `interrupt()` payload 原样包含 `kind/question/options`；
  - `interrupt()` 的恢复值直接作为 Tool 结果返回。
- `src/agents/leaderagent/agent.py:get_agent`
  - Resume 后端链路完成后，把 `ask_user` 与现有 MCP tools 一起传给 `_build_agent`；
  - 不新增工具注册器，不向 SubAgent 扩散。
- `server/service/thread_service.py:save_message_from_langgraph_state`
  - 按稳定 message ID 增量保存或 upsert；
  - ToolMessage 继续按 `tool_call_id` 关联 ToolCall；
  - Resume checkpoint 重读不重复保存历史消息；
  - 保持当前 `None` 返回值，不承载 interrupt 检测。

```python
@tool
def ask_user(question: str, options: list[str]) -> str:
    return str(
        interrupt(
            {
                "kind": "ask_user",
                "question": question,
                "options": options,
            }
        )
    )
```

### 2.7 Frontend and refresh

- `web/src/types/chat.ts`
  - 增加 `interrupted`、`InteractionRequired`、Resume request/response、
    `active_run/pending_interaction` 类型；`InteractionRequired` 包含 `question` 和
    `options: string[]`。
- `web/src/api/agent.ts`
  - 新增 `resumeAgentRun(parentRunId, request)`。
- `web/src/composables/useAgentRun.ts`
  - 保存 pending interaction；提交 `thread_metadata.resume`；
  - 使用响应中的新 Run ID、状态和 Stream URL 替换当前 Run。
- `server/service/thread_service.py:get_thread_detail_service`
  - 返回 active Run 和尚无 Resume 子 Run 的最新 pending interaction。
- `web/src/views/ChatView.vue`
  - 组合 `ChatAskUserComponent`；待回答时禁止普通提交。
- `web/src/components/chat/hil/ChatAskUserComponent.vue`
  - 展示问题和单选 options，选择后发出 answer 事件，不直接请求 API。

## 3. Failure Handling

- 父 Run 校验失败时不创建或入队 Resume Run；
- 入队失败沿用现有 failed 收敛；
- checkpoint 缺失时新 Resume Run 写为 failed，不重放父输入；
- Stream 未产生任何停止 status 就自然耗尽时按协议错误写 failed，不得默认 completed；
- PostgreSQL 已提交但 Redis 发布失败时，以数据库状态和 metadata 收敛；
- 父行锁和 Resume 子 Run 查询串行化并发恢复。

## 4. Validation

- LangGraph 1.2.9 interrupt/resume fixture 验证暂停后 `StateSnapshot.interrupts` 的真实结构；
- `check_agent_interrupt_handler` 的无打断、单个/多个 interrupt 测试；
- `build_agent_interrupt_message` 的 question/options 正常与非法结构测试；
- Repository 的 interrupted、父行锁、幂等和重复恢复测试；
- Resume Service 的权限、Thread、`thread_metadata.resume` 和新旧 Run ID 测试；
- Worker 的 finished/error/failed/interrupted 分支、自然耗尽、`changed=True/False` 和
  PostgreSQL -> interaction -> end 顺序测试；
- ToolCall/ToolMessage 幂等持久化和再次 interrupt 测试；
- 前端状态流、刷新恢复、重复提交禁用、ESLint、TypeScript 和生产构建；
- Ruff/compileall、文档链接和 `git diff --check`。

## 5. Scope Limits

- 不新增 Interaction/Approval Repository 或额外 Redis 基础设施；
- 不把 checkpoint、问题或回答保存到浏览器；
- 不实现审批、表单、多选、多问题或 SubAgent HIL；
- 只新增 BaseAgent Resume stream 入口，不新建第二套 chunk、持久化或 Worker 事件协议；
- 不新增独立 interrupt processor 模块；
- 不保留新旧两套 Resume API。
