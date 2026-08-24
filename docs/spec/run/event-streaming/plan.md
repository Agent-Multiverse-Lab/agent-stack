# Implementation Plan: Run Event Streaming

计划版本：`v0.3.0`

当前版本位于正文；已被替代的完整计划保留在文末“历史版本”中。

## 1. Implementation Steps

1. 修改 `src/agents/base_agent.py:BaseAgent.stream_messages_with_event`，只识别当前
   LangChain v3 的 `messages`、`values` 和 `tools` channel；保留 `params.data` 与
   `params.namespace`，删除未使用的 v2 兼容分支和 `tool` 单数分支。
2. 修改 `server/service/thread_service.py:stream_agent_response` 及其 message
   dispatcher：消息统一投影为 `message_delta/message_id/thread_id/content_delta`，
   values 投影为 `agent_state`，tools 投影为 LangChain v3 的工具生命周期事件；
   使用实际解析到的子线程 ID，异常直接向 Worker 传播。
3. 修改 `server/worker.py:map_stream_event` 和 `StreamEventSmoother`：内部
   `chunk.status` 只选择 `status/messages/values/agent_execute_event/end`，写入
   `messages` 时只保存标准 `AgentMessage` item，不保存原始 chunk。
4. 保留 `server/service/arq_queue_servcie.py` 的现有 envelope 和 XADD 行为；不新增
   `run_type`、`seq` 或第二个事件 builder。
5. 在 `server/router/agent_router.py:create_agent_run` 的响应中增加当前 Run 的
   `run_type`；历史消息继续使用现有 `ThreadRunMetadataResponse.run_type`。
6. 调整 `server/router/agent_router.py:stream_run_event`，读取并校验可选
   `Last-Event-ID`；调整 `server/service/agent_run_service.py:stream_agent_run_events`
   从该 Redis Stream ID 之后读取。
7. 完成现有 PostgreSQL 驱动终止计划：每轮重查 `AgentRun.agent_status`，Redis
   `end` 只唤醒重查，数据库终态前排空普通事件，再生成唯一公共 SSE `end`。
8. 在 `web/src/types/chat.ts` 定义 `AgentRunEventType`、`AgentMessage`、工具生命周期
   payload 和完整 `AgentRunEvent` 判别联合；公共事件基类包含从 SSE `id:` 取得的
   `event_id`。
9. 将 `web/src/api/chat.ts:waitForAgentRunEnd` 改为逐帧消费函数：解析
   `id/event/data`、校验联合类型、把每个事件交给调用方并返回最终 `end`；重连时
   发送最后成功处理的 `Last-Event-ID`。
10. 修改 `web/src/composables/useChat.ts`，按外层 `type` 更新 Run UI 状态、流式
    Assistant `ThreadMessageResponse`、最新 Agent state 和工具执行状态。新增
    `web/src/components/chat/ChatLoadingStateComponent.vue`，拥有 3x3 像素波、shimmer
    文案、经过时间和 reduced-motion 降级，同时复用于 Thread Detail
    读取和 Run 等待；`ChatView.vue` 只渲染归并后的数据，并在当前
    Run 产生首个非空 Assistant 文本或首个 Agent tool 消息后卸载等待组件。
11. 更新后端定向 unittest、前端 typecheck/build 覆盖；本次不修改 `AGENTS.md`。

## 2. Ownership

- PostgreSQL `AgentRun.agent_status`：Run 终态唯一事实来源。
- PostgreSQL `AgentRun.run_type`：Run 执行类型；创建响应和历史 DTO 暴露，不写入
  每个 Redis entry。
- Agent/Thread Service：LangChain v3 channel 到公开 payload 的投影。
- Worker `chunk.status`：写 Redis 前的内部分类，前端不可见。
- Redis Stream：普通事件的有序传输，以及已有事件流上的终态重查唤醒。
- `stream_agent_run_events`：重新读取数据库状态、排空 Redis 普通事件并生成公共
  SSE `end`。
- `format_agent_run_sse`：只格式化已经确定的 envelope，不查询数据库或 Redis。
- Frontend API adapter：SSE frame 解析、`event_id` 提取和协议校验。
- `useChat`：事件到 UI 状态的归并。

## 3. Core Examples

### 3.1 Frontend event union

目标：`web/src/types/chat.ts`

```ts
interface AgentRunEventBase {
  event_id: string
  scope: "agent_run"
  run_id: string
  thread_id: string
  created_at: IsoDateTime
}

interface AgentMessage {
  type: "message_delta"
  message_id: string
  thread_id: string
  content_delta: string
}

type AgentRunEvent =
  | (AgentRunEventBase & { type: "status"; status: string })
  | (AgentRunEventBase & { type: "messages"; items: AgentMessage[] })
  | (AgentRunEventBase & { type: "values"; agent_state: JsonObject })
  | AgentRunExecuteEvent
  | AgentRunEndEvent
```

不创建 `ChunkStatus` 前端类型；`chunk.status` 不属于公开协议。

### 3.2 Agent message projection

目标：`server/service/thread_service.py:stream_agent_response`、
`server/worker.py:StreamEventSmoother.release`

```python
message = {
    "type": "message_delta",
    "message_id": message_id,
    "thread_id": event_thread_id,
    "content_delta": text,
}

await write_stream_event(
    run_id,
    "messages",
    {"items": messages},
    event_thread_id,
)
```

`messages` payload 不再包含 `status="loading"`、`response`、`stream_event` 或原始
LangChain metadata。

### 3.3 SSE cursor

目标：`server/router/agent_router.py:stream_run_event`、
`web/src/api/chat.ts`

```python
last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None

stream_agent_run_events(
    run_id=run_id,
    current_uid=current_user.uid,
    thread_id=thread_id,
    after_id=last_event_id or "0-0",
)
```

```ts
const headers = lastEventId
  ? { "Last-Event-ID": lastEventId }
  : undefined
```

SSE parser 从 `id:` 取得 `event_id` 并附加到解析后的事件对象；不拆分 Redis ID。

### 3.4 Frontend event reduction

目标：`web/src/composables/useChat.ts:monitorRun`

```ts
const applyRunEvent = (event: AgentRunEvent) => {
  if (event.type === "messages") {
    for (const item of event.items) appendMessageDelta(item)
  } else if (event.type === "status") {
    runStatus.value = event.status
  } else if (event.type === "values") {
    agentState.value = event.agent_state
  } else if (event.type === "agent_execute_event") {
    applyToolEvent(event)
  }
}
```

流式 Assistant 消息继续复用 `ThreadMessageResponse` 形状，不新增平行的
`LocalMessage` 或 display DTO。

`Thinking...` 的可见性直接从当前 `messages + runId` 派生，不新增一份
布尔状态。当前 Run 的非空 Assistant 文本和 Agent tool 消息都属于可见输出：

```ts
// web/src/views/ChatView.vue
const hasCurrentRunVisibleOutput = computed(() =>
  messages.value.some((message) => {
    if (message.type !== "ai") return false
    const event = isRecord(message.payload.event)
      ? message.payload.event
      : null
    if (event?.run_id !== runId.value) return false
    if (message.payload.type === "tool") return true
    return message.payload.type === "text" &&
      typeof event.content === "string" &&
      event.content.trim().length > 0
  })
)
```

```vue
<!-- web/src/views/ChatView.vue -->
<ChatLoadingStateComponent
  v-if="isRunActive && !hasCurrentRunVisibleOutput"
  :key="runId ?? 'pending'"
  label="Thinking"
/>
```

等待组件只保留当前需要的 Drive 像素波，不增加 Dots、Orbit、Surfer 或
video 分支：

```vue
<!-- web/src/components/chat/ChatLoadingStateComponent.vue -->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue"

withDefaults(defineProps<{ label?: string }>(), { label: "Thinking" })

const delays = Array.from({ length: 9 }, (_, index) => {
  const row = Math.floor(index / 3)
  const column = index % 3
  return (column + Math.abs(row - 1)) * 90
})
const elapsedMs = ref(0)
const elapsed = computed(() => {
  const totalSeconds = elapsedMs.value / 1000
  if (totalSeconds < 60) return `${totalSeconds.toFixed(1)}s`
  return `${Math.floor(totalSeconds / 60)}m ${(totalSeconds % 60).toFixed(1)}s`
})
let timer: number | undefined

onMounted(() => {
  const startedAt = performance.now()
  timer = window.setInterval(() => {
    elapsedMs.value = performance.now() - startedAt
  }, 100)
})
onBeforeUnmount(() => window.clearInterval(timer))
</script>

<template>
  <div role="status" class="flex w-fit items-center gap-2.5">
    <span aria-hidden="true" class="grid grid-cols-3 gap-[1.5px]">
      <span
        v-for="(delay, index) in delays"
        :key="index"
        class="loading-pixel size-1 rounded-[1px] bg-graphite"
        :style="{ animationDelay: `${delay}ms` }"
      />
    </span>
    <span class="loading-label text-[13px] font-medium">{{ label }}</span>
    <span class="font-utility text-xs text-slate tabular-nums">{{ elapsed }}</span>
  </div>
</template>
```

组件 scoped CSS 使用现有 `--color-graphite/--color-slate` 定义 `pixel-on` 和
`shimmer-text` keyframes；全局 reduced-motion 规则负责停止动画，不停止计时。

### 3.5 数据库优先的 SSE 循环

目标：`server/service/agent_run_service.py:stream_agent_run_events`

```python
while True:
    run = await load_current_agent_run(run_id)
    terminal = str(run.agent_status) in AGENT_RUN_TERMINAL_STATUSES
    events = await read_agent_run_stream_events(
        run_id,
        after_id=after_id,
        block=not terminal,
    )

    for event_id, envelope in events:
        after_id = event_id
        if envelope["event_type"] == "end":
            continue
        yield format_agent_run_sse(event_id, envelope)

    if terminal and not events:
        yield format_agent_run_sse(
            after_id,
            build_terminal_envelope(run),
        )
        return
```

示例表达控制顺序；实现复用现有 repository、queue reader、builder 和 formatter，
不新增 `load_current_agent_run` 或 `build_terminal_envelope` 公共抽象。

### 3.6 Redis end 只负责唤醒

目标：`server/service/agent_run_service.py:stream_agent_run_events`

```python
if envelope["event_type"] == "end":
    continue  # 下一轮重新查询 PostgreSQL。
```

公共 SSE `end` 的 `status/error` 只取自下一轮读取到的数据库 Run。

### 3.7 无 Redis Stream 的执行前终态

目标：`server/worker.py:process_agent_run`、
`server/service/agent_run_service.py:stream_agent_run_events`

```python
await set_run_terminal(run_id, status="cancelled")
# Agent Stream 前不写 Redis end；SSE 的有限等待返回后重新查询数据库并生成公共 end。
```

## 4. Failure Handling

- 非法 `Last-Event-ID`：HTTP 422，不把未校验字符串交给 Redis。
- SSE frame 缺少 `id:`、`type` 或类型所需 payload：前端抛出协议错误，不静默
  当成 `end`。
- 前端只在事件成功归并后更新 last event ID；断线从上一个成功 ID 续读。
- 未知 `event_type`：后端不写入；前端不猜测为 messages/custom。
- Agent channel 解析失败：异常传播到 Worker 并落 `failed`，不得吞掉后继续
  `completed`。
- Redis `end` 先于 SSE 的数据库查询到达：只唤醒重查，不直接结束。
- 数据库已终态但仍有未消费普通事件：先按 Stream ID 排空，再生成公共 `end`。
- Redis Stream 不存在或已过期：有限等待后重新查库，数据库终态即可结束。
- Redis `end` 写入失败：数据库终态仍能在下一次状态检查时结束 SSE。
- 数据库仍非终态：不得根据 Redis payload 中的 status 生成公共 `end`。

## 5. Scope Limits

- 不新增状态表、Redis key、数据库通知、后台任务或兼容路径。
- 不修改 Redis envelope 或 Redis Stream ID 语义。
- 不新增 `seq`、`sequence`、`sequential` 或前端 `ChunkStatus`。
- 不把 `run_type` 重复写入每个 Redis entry。
- 不把数据库查询放入 `format_agent_run_sse` 或队列服务。
- 不新增前端 Store、EventSource 包装、runtime schema 依赖或第二套 Message DTO。
- 本计划不新增最终 Assistant Message 持久化；该缺口属于 Run 完成与 Thread Message
  持久化边界，不能塞进 Redis/SSE formatter。

## 6. Validation

- 运行 `test/test_agent_run_service.py` 与
  `test/test_worker_stream_event_smoother.py` 中的定向 `unittest`。
- 增加 Agent channel 投影测试，覆盖 message、values、tools 和异常传播。
- 从 `web/` 运行 `npm run typecheck`、`npm run lint` 和 `npm run build`。
- 对变更的 Agent、service、Worker 和测试文件运行 `compileall`。
- 运行 `git diff --check`，并确认 `chunk.status` 未出现在前端类型和消费代码中。

## 7. 历史版本

以下快照仅用于保留计划演进记录，不属于当前执行范围。

<details>
<summary>计划版本：v0.2.2</summary>

## 1. Implementation Steps

1. 复用 `server/service/arq_queue_servcie.py:build_agent_chunk_envolope` 作为唯一
   envelope builder；`write_agent_run_stream_event` 的事件体参数统一命名为
   `payload`，继续负责 JSON 序列化和 Redis Stream 写入，不新增事件类或第二个
   builder。
2. 在 `server/service/agent_run_service.py` 删除无调用的
   `publish_agent_run_event` 和旧 `_build_agent_run_event`。
3. 保留 `read_agent_run_events`、`read_subagent_progress` 和
   `stream_agent_run_events` 的 Run 级编排；读取逻辑适配
   `event_type + payload` envelope，终止判断改用 `event_type=end`。
4. 新增 `server/utils/agent_run_utils.py:format_agent_run_sse`，仅完成 Redis
   envelope 到现有扁平 SSE frame 的转换。
5. `stream_agent_run_events` 的数据库终态兜底调用队列服务 builder，再调用
   SSE formatter；不在 AgentRunService 内手写 envelope，也不写回 Redis。
6. 在 `server/worker.py` 新增两个薄包装：普通事件统一调用
   `write_stream_event`，终态事件统一调用 `write_end_stream_event`。后者只固定
   `event_type="end"` 并把同名 `payload` 原样传给前者，不承担数据库终态、协程
   停止、缓冲刷新、取消信号清理或异常转换。
7. Worker 现有普通事件写入点改为调用 `write_stream_event`；
   `_finalize_run` 在数据库终态确实发生变化后调用 `write_end_stream_event`，
   其他调用点不直接写 `event_type="end"`。
8. 更新现有测试和 `AGENTS.md` 的当前职责说明，不修改前端契约、Redis key、
   TTL 或队列服务公开契约。

## 2. Naming Contract

- `event_type`：Redis/SSE 的事件类别和路由名称。
- `payload`：当前 `event_type` 的事件体，可以是 Agent 输出的投影，也可以是
  Worker 产生的生命周期数据。
- `envelope`：由 `run_id`、`event_type`、`thread_id`、`payload` 和
  `created_at` 组成的完整 Redis 事件。
- `write_agent_run_stream_event`、`write_stream_event` 和
  `write_end_stream_event` 对同一事件体统一使用参数名 `payload`；不再在相邻层
  交替使用 `event`、`data` 或 `chunk` 指代它。

当前 Worker 的三个 Redis 写入点中：

1. `StreamEventSmoother.release` 写入 `messages`，payload 是 Agent chunk 列表；
2. `process_agent_run` 写入 `status/running`，payload 是 Worker 生命周期数据；
3. `map_stream_event` 产生的 payload 来自 Agent chunk 的事件投影。

因此 `payload` 描述的是 envelope 中的位置和职责，不描述数据生产者。

## 3. Core Examples

### 3.1 Redis 写入

目标：`server/service/arq_queue_servcie.py:write_agent_run_stream_event`

该方法签名中的事件体参数命名为 `payload`：

```python
await write_agent_run_stream_event(
    run_id,
    "status",
    {"status": "running"},
    thread_id,
    ttl_seconds=RUN_REDIS_TTL_SECONDS,
)
```

该方法内部调用现有 `build_agent_chunk_envolope`；调用方不预先构造 envelope。

### 3.2 Worker 写入包装

目标：`server/worker.py:write_stream_event`、
`server/worker.py:write_end_stream_event`

```python
async def write_stream_event(
    run_id: str,
    event_type: str,
    payload: dict[str, Any],
    thread_id: str | None = None,
) -> str:
    return await write_agent_run_stream_event(
        run_id,
        event_type,
        payload,
        thread_id,
        ttl_seconds=RUN_REDIS_TTL_SECONDS,
    )


async def write_end_stream_event(
    run_id: str,
    payload: dict[str, Any],
    thread_id: str | None = None,
) -> str:

    return await write_stream_event(run_id, "end", payload, thread_id)
```

两个方法只表达 Worker 内部的普通写入与终态写入语义，不增加其他行为。

### 3.3 SSE 格式化

目标：`server/utils/agent_run_utils.py:format_agent_run_sse`

```python
frame = format_agent_run_sse(
    event_id,
    {
        "run_id": run_id,
        "event_type": "end",
        "thread_id": thread_id,
        "payload": {"status": "completed"},
        "created_at": created_at,
    },
)
```

输出仍为 `event: end`，且 `data` 保持前端当前使用的
`scope/type/run_id/thread_id/status/created_at` 扁平字段。

### 3.4 数据库终态兜底

目标：`server/service/agent_run_service.py:stream_agent_run_events`

```python
envelope = build_agent_chunk_envolope(
    run_id=run_id,
    event_type="end",
    thread_id=thread_id,
    payload={"status": status, "error": error},
    created_at=datetime.now(UTC).isoformat(),
)
yield format_agent_run_sse(after_id, envelope)
```

## 4. Scope Limits

- 不新增 Event model、factory、protocol 或兼容层。
- 不修改 Redis key、TTL、SSE endpoint、前端 DTO 或 Run 生命周期。
- 三个 writer 的 `payload` 含义和参数名保持一致；`write_stream_event` 不改变其
  内容，`write_end_stream_event` 只固定 `event_type="end"`。
- 两个 Worker 包装方法不负责停止 Agent 流或 Worker 任务；执行终止仍由现有
  控制流负责。

## 5. Validation

- 运行 `test/test_agent_run_service.py` 与
  `test/test_worker_stream_event_smoother.py` 中的定向 `unittest`。
- 对变更的 service、utils、Worker 和测试文件运行 `compileall`。
- 运行 `git diff --check`。
- 只修复本次包装接入直接覆盖到的 Worker 未完成代码；其余既有 Worker 改动若
  阻塞验证则单独报告。

## 6. 历史版本

以下快照仅用于保留计划演进记录，不属于当前执行范围。

<details>
<summary>计划版本：v0.2.1</summary>

### Implementation Steps

1. 复用 `server/service/arq_queue_servcie.py:build_agent_chunk_envolope` 作为唯一
   envelope builder；`write_agent_run_stream_event` 继续负责 JSON 序列化和 Redis
   Stream 写入，不新增事件类或第二个 builder。
2. 在 `server/service/agent_run_service.py` 删除无调用的
   `publish_agent_run_event` 和旧 `_build_agent_run_event`。
3. 保留 `read_agent_run_events`、`read_subagent_progress` 和
   `stream_agent_run_events` 的 Run 级编排；读取逻辑适配
   `event_type + payload` envelope，终止判断改用 `event_type=end`。
4. 新增 `server/utils/agent_run_utils.py:format_agent_run_sse`，仅完成 Redis
   envelope 到现有扁平 SSE frame 的转换。
5. `stream_agent_run_events` 的数据库终态兜底调用队列服务 builder，再调用
   SSE formatter；不在 AgentRunService 内手写 envelope，也不写回 Redis。
6. 在 `server/worker.py` 新增两个薄包装：普通事件统一调用
   `write_stream_event`，终态事件统一调用 `write_end_stream_event`。后者只固定
   `event_type="end"` 并复用前者，不承担数据库终态、协程停止、缓冲刷新、取消
   信号清理或异常转换。
7. Worker 现有普通事件写入点改为调用 `write_stream_event`；
   `_finalize_run` 在数据库终态确实发生变化后调用 `write_end_stream_event`，
   其他调用点不直接写 `event_type="end"`。
8. 更新现有测试和 `AGENTS.md` 的当前职责说明，不修改前端契约、Redis key、
   TTL 或队列服务公开契约。

### Core Examples

#### Redis 写入

目标：`server/service/arq_queue_servcie.py:write_agent_run_stream_event`

```python
await write_agent_run_stream_event(
    run_id,
    "status",
    {"status": "running"},
    thread_id,
    ttl_seconds=RUN_REDIS_TTL_SECONDS,
)
```

该方法内部调用现有 `build_agent_chunk_envolope`；调用方不预先构造 envelope。

#### Worker 写入包装

目标：`server/worker.py:write_stream_event`、
`server/worker.py:write_end_stream_event`

```python
async def write_stream_event(
    run_id: str,
    event_type: str,
    event: dict[str, Any],
    thread_id: str | None = None,
) -> str:
    return await write_agent_run_stream_event(
        run_id,
        event_type,
        event,
        thread_id,
        ttl_seconds=RUN_REDIS_TTL_SECONDS,
    )


async def write_end_stream_event(
    run_id: str,
    event: dict[str, Any],
    thread_id: str | None = None,
) -> str:
    return await write_stream_event(run_id, "end", event, thread_id)
```

两个方法只表达 Worker 内部的普通写入与终态写入语义，不增加其他行为。

#### SSE 格式化

目标：`server/utils/agent_run_utils.py:format_agent_run_sse`

```python
frame = format_agent_run_sse(
    event_id,
    {
        "run_id": run_id,
        "event_type": "end",
        "thread_id": thread_id,
        "payload": {"status": "completed"},
        "created_at": created_at,
    },
)
```

输出仍为 `event: end`，且 `data` 保持前端当前使用的
`scope/type/run_id/thread_id/status/created_at` 扁平字段。

#### 数据库终态兜底

目标：`server/service/agent_run_service.py:stream_agent_run_events`

```python
envelope = build_agent_chunk_envolope(
    run_id=run_id,
    event_type="end",
    thread_id=thread_id,
    payload={"status": status, "error": error},
    created_at=datetime.now(UTC).isoformat(),
)
yield format_agent_run_sse(after_id, envelope)
```

### Scope Limits

- 不新增 Event model、factory、protocol 或兼容层。
- 不修改 Redis key、TTL、SSE endpoint、前端 DTO 或 Run 生命周期。
- `write_stream_event` 不改变参数内容；`write_end_stream_event` 只固定
  `event_type="end"`。
- 两个 Worker 包装方法不负责停止 Agent 流或 Worker 任务；执行终止仍由现有
  控制流负责。

### Validation

- 运行 `test/test_agent_run_service.py` 与
  `test/test_worker_stream_event_smoother.py` 中的定向 `unittest`。
- 对变更的 service、utils、Worker 和测试文件运行 `compileall`。
- 运行 `git diff --check`。
- 只修复本次包装接入直接覆盖到的 Worker 未完成代码；其余既有 Worker 改动若
  阻塞验证则单独报告。

</details>

</details>

<details>
<summary>计划版本：v0.2.0</summary>

### Implementation Steps

1. 复用 `server/service/arq_queue_servcie.py:build_agent_chunk_envolope` 作为唯一
   envelope builder；`write_agent_run_stream_event` 继续负责 JSON 序列化和 Redis
   Stream 写入，不新增事件类或第二个 builder。
2. 在 `server/service/agent_run_service.py` 删除无调用的
   `publish_agent_run_event` 和旧 `_build_agent_run_event`。
3. 保留 `read_agent_run_events`、`read_subagent_progress` 和
   `stream_agent_run_events` 的 Run 级编排；读取逻辑适配
   `event_type + payload` envelope，终止判断改用 `event_type=end`。
4. 新增 `server/utils/agent_run_utils.py:format_agent_run_sse`，仅完成 Redis
   envelope 到现有扁平 SSE frame 的转换。
5. `stream_agent_run_events` 的数据库终态兜底调用队列服务 builder，再调用
   SSE formatter；不在 AgentRunService 内手写 envelope，也不写回 Redis。
6. 在 `server/worker.py` 新增两个薄包装：普通事件统一调用
   `write_stream_event`，终态事件统一调用 `write_end_stream_event`。后者只固定
   `event_type="end"` 并复用前者，不承担数据库终态、协程停止、缓冲刷新、取消
   信号清理或异常转换。
7. Worker 现有普通事件写入点改为调用 `write_stream_event`；
   `_finalize_run` 在数据库终态确实发生变化后调用 `write_end_stream_event`，
   其他调用点不直接写 `event_type="end"`。
8. 更新现有测试和 `AGENTS.md` 的当前职责说明，不修改前端契约、Redis key、
   TTL 或队列服务公开契约。

### Core Examples

#### Redis 写入

目标：`server/service/arq_queue_servcie.py:write_agent_run_stream_event`

```python
await write_agent_run_stream_event(
    run_id,
    "status",
    {"status": "running"},
    thread_id,
    ttl_seconds=RUN_REDIS_TTL_SECONDS,
)
```

该方法内部调用现有 `build_agent_chunk_envolope`；调用方不预先构造 envelope。

#### Worker 写入包装

目标：`server/worker.py:write_stream_event`、
`server/worker.py:write_end_stream_event`

```python
async def write_stream_event(
    run_id: str,
    event_type: str,
    event: dict[str, Any],
    thread_id: str | None = None,
) -> str:
    return await write_agent_run_stream_event(
        run_id,
        event_type,
        event,
        thread_id,
        ttl_seconds=RUN_REDIS_TTL_SECONDS,
    )


async def write_end_stream_event(
    run_id: str,
    event: dict[str, Any],
    thread_id: str | None = None,
) -> str:
    return await write_stream_event(run_id, "end", event, thread_id)
```

两个方法只表达 Worker 内部的普通写入与终态写入语义，不增加其他行为。

#### SSE 格式化

目标：`server/utils/agent_run_utils.py:format_agent_run_sse`

```python
frame = format_agent_run_sse(
    event_id,
    {
        "run_id": run_id,
        "event_type": "end",
        "thread_id": thread_id,
        "payload": {"status": "completed"},
        "created_at": created_at,
    },
)
```

输出仍为 `event: end`，且 `data` 保持前端当前使用的
`scope/type/run_id/thread_id/status/created_at` 扁平字段。

#### 数据库终态兜底

目标：`server/service/agent_run_service.py:stream_agent_run_events`

```python
envelope = build_agent_chunk_envolope(
    run_id=run_id,
    event_type="end",
    thread_id=thread_id,
    payload={"status": status, "error": error},
    created_at=datetime.now(UTC).isoformat(),
)
yield format_agent_run_sse(after_id, envelope)
```

### Scope Limits

- 不新增 Event model、factory、protocol 或兼容层。
- 不修改 Redis key、TTL、SSE endpoint、前端 DTO 或 Run 生命周期。
- `write_stream_event` 不改变参数内容；`write_end_stream_event` 只固定
  `event_type="end"`。
- 两个 Worker 包装方法不负责停止 Agent 流或 Worker 任务；执行终止仍由现有
  控制流负责。

### Validation

- 运行 `test/test_agent_run_service.py` 与
  `test/test_worker_stream_event_smoother.py` 中的定向 `unittest`。
- 对变更的 service、utils、Worker 和测试文件运行 `compileall`。
- 运行 `git diff --check`。
- 只修复本次包装接入直接覆盖到的 Worker 未完成代码；其余既有 Worker 改动若
  阻塞验证则单独报告。

</details>

<details>
<summary>计划版本：v0.1.0</summary>

### Implementation Steps

1. 复用 `server/service/arq_queue_servcie.py:build_agent_chunk_envolope` 作为唯一
   envelope builder；`write_agent_run_stream_event` 继续负责 JSON 序列化和 Redis
   Stream 写入，不新增事件类或第二个 builder。
2. 在 `server/service/agent_run_service.py` 删除无调用的
   `publish_agent_run_event` 和旧 `_build_agent_run_event`。
3. 保留 `read_agent_run_events`、`read_subagent_progress` 和
   `stream_agent_run_events` 的 Run 级编排；读取逻辑适配
   `event_type + payload` envelope，终止判断改用 `event_type=end`。
4. 新增 `server/utils/agent_run_utils.py:format_agent_run_sse`，仅完成 Redis
   envelope 到现有扁平 SSE frame 的转换。
5. `stream_agent_run_events` 的数据库终态兜底调用队列服务 builder，再调用
   SSE formatter；不在 AgentRunService 内手写 envelope，也不写回 Redis。
6. 更新现有测试和 `AGENTS.md` 的当前职责说明，不修改前端契约和 Worker
   执行流程。

### Core Examples

#### Redis 写入

目标：`server/service/arq_queue_servcie.py:write_agent_run_stream_event`

```python
await write_agent_run_stream_event(
    run_id,
    "status",
    {"status": "running"},
    thread_id,
    ttl_seconds=RUN_REDIS_TTL_SECONDS,
)
```

该方法内部调用现有 `build_agent_chunk_envolope`；调用方不预先构造 envelope。

#### SSE 格式化

目标：`server/utils/agent_run_utils.py:format_agent_run_sse`

```python
frame = format_agent_run_sse(
    event_id,
    {
        "run_id": run_id,
        "event_type": "end",
        "thread_id": thread_id,
        "payload": {"status": "completed"},
        "created_at": created_at,
    },
)
```

输出仍为 `event: end`，且 `data` 保持前端当前使用的
`scope/type/run_id/thread_id/status/created_at` 扁平字段。

#### 数据库终态兜底

目标：`server/service/agent_run_service.py:stream_agent_run_events`

```python
envelope = build_agent_chunk_envolope(
    run_id=run_id,
    event_type="end",
    thread_id=thread_id,
    payload={"status": status, "error": error},
    created_at=datetime.now(UTC).isoformat(),
)
yield format_agent_run_sse(after_id, envelope)
```

### Scope Limits

- 不新增 Event model、factory、protocol 或兼容层。
- 不修改 Redis key、TTL、SSE endpoint、前端 DTO 或 Run 生命周期。
- 不修改当前工作区中的 `server/worker.py` 未提交改动。

### Validation

- 运行 `test/test_agent_run_service.py` 中的定向 `unittest`。
- 对变更的 service、utils 和测试文件运行 `compileall`。
- 运行 `git diff --check`。
- 单独报告当前 `server/worker.py` 未完成改动导致的全量后端编译阻塞，不在本任务中代为修复。

</details>
