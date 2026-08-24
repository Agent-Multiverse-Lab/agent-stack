# Agent Run Event Streaming Spec

## 1. Goal

本能力只打通一个顶层 Chat Agent Run：前端创建 Run，Worker 独立执行并写入
Redis Stream，前端通过 SSE 读取消息，断线后继续读取，并可请求停止当前 Run。

Worker 的执行生命周期不得依赖某一条 SSE 连接。前端断开不会停止 Run；重新连接
必须继续读取同一个 `run_id`，只有取消接口或 Worker 终态才能结束执行。

本规格以后端现有公开接口和 Worker 真实写入内容为合同来源，不包含模拟数据。

## 2. Scope

本次范围：

- 单个用户、单个 `thread_id`、单个顶层 Agent Run；
- `POST /api/agent/runs` 创建并入队；
- Worker 与 SSE Reader 的读写分离；
- Redis Stream 消息、状态和终态事件；
- 同一个 `run_id` 的断线续读；
- 刷新后从 `localStorage` 恢复未结束 Run 的 Stream 快照，并从 Redis Stream 起点
  重放内容；
- `POST /api/agent/runs/{run_id}/cancel` 协作式取消；
- 终态后重新加载 PostgreSQL 中的历史消息。

本次不包含：

- SubAgent、`parent_run_id`、父子 Run 或子线程聚合；
- 根据 `run_type` 分支执行；
- Human-in-the-loop resume；
- 为每一种 Run Event 建立一个 TypeScript interface；
- 新的 Redis key、事件总线或 Pinia 持久化插件。

## 3. Backend HTTP contracts

### 3.1 Create Run

接口：`POST /api/agent/runs`

当前主链请求字段：

| 字段 | 类型 | 必需 | 含义 |
| --- | --- | --- | --- |
| `query` | string \| null | 否 | 用户输入文本 |
| `agent_id` | string | 是 | 当前对话绑定的顶层 Agent |
| `thread_id` | string | 是 | 当前对话 ID |
| `thread_metadata` | object | 否 | Run 元数据 |
| `msg_metadata` | object | 否 | 输入消息元数据和附件 ID |
| `image_content` | string \| null | 否 | 当前输入图像内容 |

`is_resume` 和 `parent_run_id` 即使仍存在于当前后端请求 Schema，也不由本次前端
发送或消费。

真实响应字段：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `run_id` | string | 新建 Run ID |
| `run_type` | string | 后端记录的 Run 类型；当前主链返回 `chat` |
| `thread_id` | string | 所属对话 ID |
| `status` | string | 创建后的持久化 Run 状态 |
| `request_id` | string \| null | 本次请求 ID |
| `stream_url` | string | 当前 Run 的 SSE 地址 |

当前 Router 还没有返回 `run_type`；本次实现从 `AgentRun.run_type` 补入响应。前端
不发送或推导该字段，也不根据它进入 SubAgent 分支。创建 Run 后直接使用后端返回的
`stream_url`；只有从 Thread Detail 恢复已有活动 Run 时，才根据公开路由和已有
`run_id/thread_id` 重建同一地址。

### 3.2 Get Run status

接口：`GET /api/agent/runs/{run_id}`

| 输入 | 位置 | 必需 | 含义 |
| --- | --- | --- | --- |
| `run_id` | path | 是 | 要核实的 Run |
| `thread_id` | query | 是 | 校验 Run 所属对话 |
| Bearer token | header | 是 | 校验当前用户 |

响应只返回恢复流程需要的字段：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `run_id` | string | 当前 Run |
| `run_type` | string | 后端记录的 Run 类型 |
| `thread_id` | string | 所属对话 |
| `status` | string | PostgreSQL 当前 Run 状态 |

当前后端尚无该接口，本次实现需要增加。它只读取 PostgreSQL，不读取 Redis Stream。

### 3.3 Read Run events

接口：`GET /api/agent/runs/{run_id}/events`

| 输入 | 位置 | 必需 | 含义 |
| --- | --- | --- | --- |
| `run_id` | path | 是 | 要读取的 Run |
| `thread_id` | query | 是 | 校验 Run 所属对话 |
| Bearer token | header | 是 | 校验当前用户 |
| `Last-Stream-ID` | header | 否 | 最后成功处理的 Redis Stream ID |

响应为 `text/event-stream`。后端必须同时使用 `run_id + thread_id + 当前用户` 校验
读取权限。

`Last-Stream-ID` 是本项目的自定义请求 Header；SSE 响应仍使用标准 `id:` field
承载 Redis Stream ID。

当前 Router 尚未接收 `Last-Stream-ID`，`stream_agent_run_events()` 也固定从 `0-0`
开始；本次实现需要补上该 header，并从指定 Redis Stream ID 之后读取。

### 3.4 Cancel Run

接口：`POST /api/agent/runs/{run_id}/cancel`

真实响应字段：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `run_id` | string | 被请求取消的 Run |
| `thread_id` | string | 所属对话 ID |
| `agent_id` | string | 执行 Agent |
| `status` | string | 持久化后的当前状态 |

取消响应通常返回 `cancel_requested`。它只表示停止请求已经持久化，不表示 Worker
已经停止；前端必须继续读取同一个 SSE，直到收到 `cancelled` 终态。

### 3.5 Reload thread

接口：`GET /api/chat/thread/{thread_id}`

前端在进入对话和 Run 终态后继续使用现有 `ThreadDetailResponse`。历史消息以
PostgreSQL `ThreadMessageResponse` 为准；当前活动 Run 从消息关联的 `run_id` 和
`status` 恢复，不建立第二套本地 Message DTO。

## 4. Ownership and flow

```text
Frontend
  -> POST /api/agent/runs
  -> receive run_id + thread_id + stream_url
  -> save runtime state to Pinia
  -> save initial Active Run snapshot to localStorage
  -> startAgentRunStream(stream_url)

Worker
  -> load Run and input Message from PostgreSQL
  -> execute Agent
  -> XADD run:events:{run_id}

Frontend
  -> GET stream_url
  -> read SSE independently
  -> apply each SSE event to the UI
  -> replace the Active Run snapshot in localStorage
  -> POST /api/agent/runs/{run_id}/cancel when requested
```

状态所有权：

| 数据 | 所有者 | 用途 |
| --- | --- | --- |
| Run ID 和状态 | PostgreSQL `AgentRun` | Run 身份及生命周期唯一事实来源 |
| 输入和最终消息 | PostgreSQL `Message` | 历史消息唯一事实来源 |
| 流式事件 | Redis Stream | Worker 与 SSE Reader 之间的有序传输 |
| 当前运行态 | Pinia Chat Store | 当前页面和路由内的响应式 Run 状态 |
| Active Run 快照 | `localStorage` | 保存当前 Run 和最近一次已消费 SSE 的位置，不保存消息内容 |

## 5. Worker write contract

Stream Key 为 `run:events:{run_id}`。当前四条真实写入路径为：

| `event_type` | payload 形成位置 | payload |
| --- | --- | --- |
| `status` | `process_agent_run()` | `status=running` |
| `messages` | `StreamEventSmoother.release()` | `items` 为完整 loading chunk 数组 |
| `custom` | `map_stream_event()` | `name=agent_state`、完整 `chunk` 和 `agent_state` |
| `end` | `_finalize_run()` 或执行中取消分支 | PostgreSQL 实际终态及可选错误信息 |

`loading` chunk 在主循环中先进入 `StreamEventSmoother`，释放时以 `messages` 写入。
`agent_state` 由 `map_stream_event()` 映射为 `custom`。`finished` 的映射返回值不会
直接写入；最终 `end` 由持久化终态形成。

Redis entry 只包含两个 field：

| Redis field | 类型 | 含义 |
| --- | --- | --- |
| `event_type` | string | 读取侧路由字段 |
| `event` | JSON string | 完整 envelope |

Envelope 字段：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `run_id` | string | 当前 Run |
| `event_type` | string | 当前事件路由字段 |
| `thread_id` | string \| null | 事件所属线程 |
| `payload` | object | 由对应 Worker 写入点形成的内容 |
| `created_at` | string | Redis 写入时间 |

Queue writer 只负责 envelope、JSON 序列化和 `XADD`，不得解释 Agent chunk。

当前 Redis Stream 不是永久历史：`XADD` 使用
`config.run_stream_max_len`（默认 `10000`）近似裁剪，并在每次写入后设置
`RUN_REDIS_TTL_SECONDS`（当前为 24 小时）TTL。因此 Redis 只承担重放窗口；
PostgreSQL Thread Detail 仍是终态历史来源。

## 6. Agent message contract

`messages` 的 payload 只有 `items`。`items` 中每一项都是当前 Worker 保存的完整
loading chunk：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `request_id` | string \| null | 本次请求 ID |
| `response` | string | 当前兼容字段；前端不把它作为文本来源 |
| `thread_id` | string | 当前线程 |
| `status` | string | 当前值为 `loading` |
| `stream_event` | array | 标准化后的 Agent Message |
| `metadata` | object | LangChain message metadata |

`stream_event` item 的公共字段：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `type` | string | item 路由字段 |
| `message_id` | string | 流式消息关联 ID |
| `thread_id` | string | 所属线程 |

当前文本 item 使用 `type=message_delta` 和 `content_delta`。当前工具调用 item 使用
`type=tool_call`，并携带 `tool_call_id/name/args/index`。这些只是同一数组中的不同
消息内容，不要求分别建立 TypeScript 实体。

流式字符串 `message_id` 不是 PostgreSQL 数字型 `ThreadMessageResponse.message_id`。

## 7. Public SSE contract

每个 SSE frame 包含：

| SSE field | 来源 | 前端用途 |
| --- | --- | --- |
| `id` | Redis Stream entry ID | 顺序、去重和续读 cursor |
| `event` | Redis `event_type` | 浏览器/SSE 路由字段 |
| `data` | 扁平化 envelope 和 payload | 页面消费内容 |

`data` 中的公共字段为 `scope/type/run_id/thread_id/created_at`。payload 字段直接展开
到 `data` 顶层。

前端最多保留一个通用事件对象：公共字段加任意 payload 字段。`type` 是字符串；
新增事件类型不要求新增 interface。消费者只在处理自己关心的 `type` 时校验对应
字段。

## 8. Sticky Run and reconnect

粘性属于 `run_id + thread_id`，不属于某一条 HTTP/SSE 连接：

- 创建 Run 后，前端把完整运行态写入 Pinia，并创建一份不含消息内容的 Active Run
  快照；
- SSE 断开不会取消 Worker；
- 同一页面重连继续请求原 `stream_url`，不得创建新 Run；
- 每个 SSE event 成功解析和渲染后，更新 Pinia，并用最新 `lastStreamId` 覆盖
  localStorage 中同一个 Active Run 快照；
- 页面未刷新且 Pinia 中的当前 Run 仍在内存时，任何续连都把
  `lastStreamId` 作为 `Last-Stream-ID` 发送，从该 Redis Stream ID 之后继续读取；
- 整页刷新导致 Pinia 消息内容丢失后，从 localStorage 恢复 Active Run 快照，但不把
  快照中的 `lastStreamId` 用作本次读取起点，而是从 Redis Stream 起点重放；
- 用户流程中的 sequential 直接使用 Redis Stream ID，不新增另一套整数序号；
- 收到终态后重新读取 Thread Detail，用 PostgreSQL 最终消息替换流式显示。

Storage key 命名为 `active_run:{threadId}`。一个 key 只保存当前对话未结束 Run 的
最新快照；每次事件覆盖旧快照，不追加本地事件列表：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `threadId` | string | 当前对话 |
| `runId` | string | 当前 Run |
| `lastStreamId` | string \| null | 最近一次已经成功解析并渲染的 SSE `id` |

保存方法固定为第 10.2 节的 `saveActiveRunSnapshot()`，不再定义第二套快照写入方法。

创建 Run 后以 `lastStreamId=null` 写入初始快照。之后每收到一个合法 SSE event，使用
该 event 的 `id` 再调用一次 `saveActiveRunSnapshot()`，覆盖同一个 key。快照不得保存
`messages.items`、文本增量、完整 SSE `data`、已渲染 `content` 或 Agent state。

刷新恢复顺序：

1. 根据路由 `thread_id` 读取对应的 localStorage Active Run 快照；
2. 使用 `run_id + thread_id` 调用 Run 状态接口核实 PostgreSQL 当前状态；
3. 状态为 `pending/running/cancel_requested` 时，清空 Pinia 中该 Run 的临时输出，
   使用快照中的 `runId + threadId` 重建 SSE 地址，不发送快照中的 `lastStreamId`，
   由后端从 `0-0` 开始读取；
4. 前端按 Redis Stream 顺序重新归并事件，在 Pinia 中重建内容和
   `lastStreamId`，并在每个事件后覆盖 localStorage 快照；
5. 状态为 `completed/failed/cancelled` 时，不重连 SSE，直接读取 Thread Detail，
   以数据库最终消息替换 Pinia 内容并删除 Active Run 快照；
6. SSE 收到 `end` 后执行同一 Thread Detail 收口流程；
7. 快照损坏、Run 不存在或不属于当前用户时删除快照，再按普通 Thread Detail
   加载；
8. Redis Stream 已过期或已裁剪到不能重建完整内容时，不把 Redis 当作历史数据库，
   改读 Thread Detail；若 Run 仍在执行，页面只展示当前仍可重放的运行态内容，终态后
   再以 PostgreSQL 最终消息收口。

`localStorage` 只保存 Active Run 快照，不是 Run 状态或历史消息的事实来源。登出时
必须清理当前用户的未结束 Run 快照，避免同一浏览器上的其他账号读取。

## 9. Stop flow

```text
pending/running
  -> POST cancel
  -> PostgreSQL cancel_requested
  -> Redis cancel key + Pub/Sub
  -> Worker stops Agent stream
  -> flush buffered messages
  -> PostgreSQL cancelled
  -> SSE end(status=cancelled)
```

约束：

- 前端点击停止只能调用取消接口，不能通过关闭 SSE 代替取消；
- 收到 `cancel_requested` 后按钮进入停止中，但 SSE 保持连接；
- Worker 停止并排空已经产生的消息后才能写 `cancelled`；
- `completed/failed/cancelled` 是终态；
- Redis `end` 丢失或 Stream 尚未创建时，SSE Reader 仍以 PostgreSQL 终态收口；
- 前端取消请求只提交目标 `run_id`，不发起任何 child Run 操作。

## 10. Frontend minimum behavior

前端只修改以下现有边界并新增一个 Chat Store：

| 文件 | 定义 |
| --- | --- |
| `web/src/types/chat.ts` | HTTP DTO、单个通用 SSE event、Active Run snapshot |
| `web/src/stores/useChatStore.ts` | 当前 Run 的 Pinia 运行态和 snapshot 读写动作 |
| `web/src/api/chat.ts` | Run 状态请求和原始 SSE 流读取 |
| `web/src/composables/useChat.ts` | Run 启动、恢复、事件解释和页面状态编排 |
| `web/src/views/ChatView.vue` | 将内存中的 Assistant 流式文本交给现有 Markdown renderer |

不新增逐事件实体类、SSE 客户端类、Repository、持久化插件或新的消息 DTO。

### 10.1 TypeScript contracts

目标：`web/src/types/chat.ts`

`AgentRunCreateResponse` 补上后端 `run_type`。Active Run snapshot 只定义真实写入
localStorage 的三个字段。所有 SSE event 共用一个结构，payload 的额外字段保持
`unknown`，不为 `status/messages/custom/end` 分别建类型。

```ts
export interface AgentRunCreateResponse {
  run_id: string
  run_type: string
  thread_id: string
  status: string
  request_id: string | null
  stream_url: string
}

export interface AgentRunStatusResponse {
  run_id: string
  run_type: string
  thread_id: string
  status: string
}

export interface ActiveRunSnapshot {
  threadId: string
  runId: string
  lastStreamId: string | null
}

export type AgentRunStreamEvent = Record<string, unknown> & {
  id: string
  event: string
  scope: "agent_run"
  type: string
  run_id: string
  thread_id: string
  created_at: string
}
```

### 10.2 Pinia state and Active Run snapshot

目标：`web/src/stores/useChatStore.ts`

Store 只保存当前 Run 的内存投影。`assistantContent` 和 `agentState` 不写 localStorage。
`saveActiveRunSnapshot()` 必须保持用户指定的三个参数，并在每个 SSE event 成功处理后
覆盖同一个 key。

```ts
import { computed, ref } from "vue"
import { defineStore } from "pinia"

import type { ActiveRunSnapshot } from "@/types/chat"

const activeRunKey = (threadId: string) => `active_run:${threadId}`

const isActiveRunSnapshot = (value: unknown): value is ActiveRunSnapshot => {
  if (!value || typeof value !== "object") return false
  const snapshot = value as Record<string, unknown>
  return typeof snapshot.threadId === "string" &&
    typeof snapshot.runId === "string" &&
    (snapshot.lastStreamId === null ||
      typeof snapshot.lastStreamId === "string")
}

export const useChatStore = defineStore("chat", () => {
  const activeThreadId = ref<string | null>(null)
  const activeRunId = ref<string | null>(null)
  const runStatus = ref<string | null>(null)
  const activeLastStreamId = ref<string | null>(null)
  const assistantContent = ref("")
  const agentState = ref<Record<string, unknown> | null>(null)

  const isRunActive = computed(() =>
    runStatus.value === "pending" ||
    runStatus.value === "running" ||
    runStatus.value === "cancel_requested"
  )

  const saveActiveRunSnapshot = (
    threadId: string,
    runId: string,
    lastStreamId: string | null
  ) => {
    const snapshot: ActiveRunSnapshot = {
      threadId,
      runId,
      lastStreamId
    }
    activeThreadId.value = threadId
    activeRunId.value = runId
    activeLastStreamId.value = lastStreamId
    localStorage.setItem(
      activeRunKey(threadId),
      JSON.stringify(snapshot)
    )
  }

  const loadActiveRunSnapshot = (
    currentThreadId: string
  ): ActiveRunSnapshot | null => {
    const key = activeRunKey(currentThreadId)
    const raw = localStorage.getItem(key)
    if (!raw) return null

    try {
      const snapshot: unknown = JSON.parse(raw)
      if (isActiveRunSnapshot(snapshot) &&
          snapshot.threadId === currentThreadId) {
        return snapshot
      }
    } catch {
      // Invalid local snapshot is removed below.
    }

    localStorage.removeItem(key)
    return null
  }

  const beginActiveRun = (
    currentThreadId: string,
    currentRunId: string,
    status: string
  ) => {
    runStatus.value = status
    assistantContent.value = ""
    agentState.value = null
    saveActiveRunSnapshot(currentThreadId, currentRunId, null)
  }

  const appendAssistantContent = (contentDelta: string) => {
    assistantContent.value += contentDelta
  }

  const clearActiveRun = (currentThreadId: string) => {
    localStorage.removeItem(activeRunKey(currentThreadId))
    if (activeThreadId.value !== currentThreadId) return
    activeThreadId.value = null
    activeRunId.value = null
    runStatus.value = null
    activeLastStreamId.value = null
    assistantContent.value = ""
    agentState.value = null
  }

  return {
    activeThreadId,
    activeRunId,
    runStatus,
    lastStreamId: activeLastStreamId,
    assistantContent,
    agentState,
    isRunActive,
    saveActiveRunSnapshot,
    loadActiveRunSnapshot,
    beginActiveRun,
    appendAssistantContent,
    clearActiveRun
  }
})
```

`runStatus` 和 `agentState` 由 `useChat.ts` 直接赋值即可，不再为一次赋值增加包装 action。

### 10.3 Run status and SSE transport

目标：`web/src/api/chat.ts`

保留现有 `authorizedFetch()`。删除只等待 `end` 的 `readSseBlock()` 和
`waitForAgentRunEnd()`，改为以下状态读取和通用 SSE reader：

```ts
import type {
  AgentRunStatusResponse,
  AgentRunStreamEvent
} from "@/types/chat"

export const getAgentRunStatus = (
  runId: string,
  threadId: string,
  accessToken: string
) =>
  authorizedJson<AgentRunStatusResponse>(
    `/api/agent/runs/${encodeURIComponent(runId)}` +
      `?thread_id=${encodeURIComponent(threadId)}`,
    accessToken
  )

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value)

const parseSseBlock = (block: string): AgentRunStreamEvent | null => {
  let id = ""
  let event = ""
  const dataLines: string[] = []

  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith("id:")) id = line.slice(3).trimStart()
    if (line.startsWith("event:")) event = line.slice(6).trimStart()
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart())
    }
  }

  if (!id || !event || dataLines.length === 0) return null
  const data: unknown = JSON.parse(dataLines.join("\n"))
  if (!isRecord(data) ||
      data.scope !== "agent_run" ||
      typeof data.type !== "string" ||
      data.type !== event ||
      typeof data.run_id !== "string" ||
      typeof data.thread_id !== "string" ||
      typeof data.created_at !== "string") {
    throw new Error("Agent Run SSE 事件格式无效")
  }

  return { ...data, id, event } as AgentRunStreamEvent
}

export async function* streamRunEvents(
  streamUrl: string,
  accessToken: string,
  lastStreamId: string | null,
  signal: AbortSignal
): AsyncGenerator<AgentRunStreamEvent> {
  const headers = new Headers()
  if (lastStreamId) headers.set("Last-Stream-ID", lastStreamId)

  const response = await authorizedFetch(streamUrl, accessToken, {
    method: "GET",
    cache: "no-store",
    headers,
    signal
  })
  if (!response.body) throw new Error("Agent Run 事件流不可读")

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })

      let separator = buffer.match(/\r?\n\r?\n/)
      while (separator?.index !== undefined) {
        const block = buffer.slice(0, separator.index)
        buffer = buffer.slice(separator.index + separator[0].length)
        const parsed = parseSseBlock(block)
        if (parsed) yield parsed
        separator = buffer.match(/\r?\n\r?\n/)
      }

      if (done) break
    }
  } finally {
    reader.releaseLock()
  }
}
```

`streamRunEvents()` 只做 HTTP、SSE framing 和公共字段校验，不读取 Pinia、localStorage
或 Vue 渲染状态。

### 10.4 Event projection and rendering

目标：`web/src/composables/useChat.ts:applyRunStreamEvent`

```ts
import { useChatStore } from "@/stores/useChatStore"
import type { AgentRunStreamEvent } from "@/types/chat"

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value)

const applyRunStreamEvent = (
  event: AgentRunStreamEvent,
  chatStore: ReturnType<typeof useChatStore>
): boolean => {
  if (typeof event.status === "string") {
    chatStore.runStatus = event.status
  }

  if (event.type === "messages" && Array.isArray(event.items)) {
    for (const item of event.items) {
      if (!isRecord(item) || !Array.isArray(item.stream_event)) continue
      for (const messageEvent of item.stream_event) {
        if (!isRecord(messageEvent)) continue
        if (messageEvent.type === "message_delta" &&
            typeof messageEvent.content_delta === "string") {
          chatStore.appendAssistantContent(messageEvent.content_delta)
        }
      }
    }
  }

  if (event.type === "custom" && isRecord(event.agent_state)) {
    chatStore.agentState = event.agent_state
  }

  return event.type === "end"
}
```

当前只渲染真实 `message_delta.content_delta`。`tool_call` 仍可被通用事件读取，但本次
不新增工具调用 UI。

### 10.5 Stream orchestration and reconnect

目标：`web/src/composables/useChat.ts:startAgentRunStream`

`initialLastStreamId` 明确区分两种入口：页面内续连传 Pinia 中的 cursor；整页刷新
重放传 `null`。

```ts
const runStreamUrl = (runId: string, threadId: string) =>
  `/api/agent/runs/${encodeURIComponent(runId)}/events` +
  `?thread_id=${encodeURIComponent(threadId)}`

const terminalRunStatuses = new Set(["completed", "failed", "cancelled"])

const finalizeActiveRun = async (
  threadId: string,
  accessToken: string
) => {
  const detail = await getThreadDetail(threadId, accessToken)
  thread.value = detail.thread
  messages.value = detail.messages
  chatStore.clearActiveRun(threadId)
}

const startAgentRunStream = async (
  threadId: string,
  runId: string,
  accessToken: string,
  initialLastStreamId: string | null
) => {
  let cursor = initialLastStreamId

  while (chatStore.activeRunId === runId && chatStore.isRunActive) {
    const controller = new AbortController()
    streamController = controller

    try {
      for await (const event of streamRunEvents(
        runStreamUrl(runId, threadId),
        accessToken,
        cursor,
        controller.signal
      )) {
        if (chatStore.activeRunId !== runId) return

        const isEnd = applyRunStreamEvent(event, chatStore)
        chatStore.saveActiveRunSnapshot(threadId, runId, event.id)
        cursor = event.id

        if (isEnd) {
          await finalizeActiveRun(threadId, accessToken)
          return
        }
      }
    } catch (caught) {
      if (controller.signal.aborted) return
      error.value = errorText(caught)
    } finally {
      if (streamController === controller) streamController = null
    }

    const run = await getAgentRunStatus(runId, threadId, accessToken)
    chatStore.runStatus = run.status
    if (terminalRunStatuses.has(run.status)) {
      await finalizeActiveRun(threadId, accessToken)
      return
    }

    await new Promise((resolve) => window.setTimeout(resolve, 1000))
    cursor = chatStore.lastStreamId
  }
}
```

创建 Run 后的调用位置：`web/src/composables/useChat.ts:submitDraft`

```ts
const run = await createAgentRun(
  query,
  currentThread.agent_id,
  currentThread.thread_id,
  attachmentSnapshot.map((attachment) => attachment.file_id),
  accessToken
)

chatStore.beginActiveRun(run.thread_id, run.run_id, run.status)
await startAgentRunStream(
  run.thread_id,
  run.run_id,
  accessToken,
  null
)
```

### 10.6 Refresh restore

目标：`web/src/composables/useChat.ts:restoreActiveRun`

```ts
const restoreActiveRun = async (
  threadId: string,
  accessToken: string
) => {
  const snapshot = chatStore.loadActiveRunSnapshot(threadId)
  if (!snapshot) return false

  const run = await getAgentRunStatus(
    snapshot.runId,
    snapshot.threadId,
    accessToken
  )

  if (terminalRunStatuses.has(run.status)) {
    await finalizeActiveRun(threadId, accessToken)
    return true
  }

  chatStore.beginActiveRun(threadId, snapshot.runId, run.status)
  await startAgentRunStream(
    threadId,
    snapshot.runId,
    accessToken,
    null
  )
  return true
}
```

刷新恢复故意传 `null`，不传 snapshot 中的 `lastStreamId`，因为 localStorage 没有保存
已经渲染的消息。页面未刷新时发生的网络续连则由 `startAgentRunStream()` 使用当前
Pinia `lastStreamId`。

### 10.7 ChatView streaming output

目标：`web/src/views/ChatView.vue`

在现有持久化 `messages` 列表之后渲染 Pinia 中的当前 Assistant 文本，不构造假的
`ThreadMessageResponse`：

```vue
<script setup lang="ts">
import { storeToRefs } from "pinia"
import MarkdownRender from "markstream-vue"

import { useChatStore } from "@/stores/useChatStore"

const chatStore = useChatStore()
const { assistantContent } = storeToRefs(chatStore)
</script>

<template>
  <article
    v-if="assistantContent"
    class="min-w-0 max-w-full leading-7 text-graphite"
    aria-live="polite"
  >
    <MarkdownRender
      mode="chat"
      :content="assistantContent"
      :final="false"
    />
  </article>
</template>
```

终态后 `finalizeActiveRun()` 重新读取 Thread Detail；`clearActiveRun()` 清空
`assistantContent`，最终 Assistant 消息由 PostgreSQL 返回的 `messages` 渲染。

`ChatLoadingStateComponent.vue` 统一渲染 Chat 的等待状态。它接收一个
`label` 文案，Thread Detail 读取传入 `Loading conversation`，活跃 Run
使用默认的 `Thinking`；组件内部显示 3x3 方形像素
波、单色 shimmer 文案和 0.1 秒精度的经过时间。组件卸载时必须清理
计时器；用户设置 reduced motion 时停止像素和 shimmer 动画，计时仍继续。

`ChatView.vue` 只决定何时挂载该组件：当前 Run 仍活跃且还没有产生
可见 Assistant 文本或 Agent tool 状态时显示；首个非空文本增量或首个 tool
消息被并入页面消息后立即隐藏。其他 Run 的历史消息和空白增量不得改变
该判断。可见性根据现有 `messages + runId` 派生，不新增 Store 字段或后端事件。

### 10.8 Stop current Run

目标：`web/src/composables/useChat.ts:cancelCurrentRun`

停止按钮只请求后端取消并更新 `cancel_requested`，不关闭 SSE，也不删除 snapshot。
最终清理由 `end` 或 PostgreSQL 终态触发。

```ts
const cancelCurrentRun = async () => {
  const runId = chatStore.activeRunId
  if (!runId || cancelling.value || !chatStore.isRunActive) return

  cancelling.value = true
  error.value = ""
  try {
    const response = await cancelAgentRun(
      runId,
      requireAccessToken()
    )
    if (chatStore.activeRunId === runId) {
      chatStore.runStatus = response.status
    }
  } catch (caught) {
    if (chatStore.activeRunId === runId) {
      error.value = errorText(caught)
    }
  } finally {
    cancelling.value = false
  }
}
```

## 11. Requirements

### RUN-ES-001 Single top-level Run

本能力只处理一个顶层 Chat Run。创建、读取和取消都以同一个
`run_id + thread_id + 当前用户` 为边界。

### RUN-ES-002 Producer-reader separation

Worker 独立执行并写 Redis Stream；SSE Reader 独立读取。SSE 连接断开不得停止或
重启 Worker。

### RUN-ES-003 Backend-owned contracts

前端使用第 3 节的后端字段。`run_type` 由后端返回；前端不自定义本地 Message DTO
或逐事件实体。

### RUN-ES-004 Ordered reconnect

Redis Stream ID 是唯一事件 cursor。后端接受 `Last-Stream-ID`，前端只在成功消费后
推进 cursor。页面未刷新且 Pinia cursor 仍在内存时，任何续连都从该 cursor 之后
读取。localStorage 快照记录该 cursor，但整页刷新时因浏览器没有消息内容，仍从
`0-0` 重放当前 Redis Stream。

### RUN-ES-005 Cooperative stop

取消必须经过 `cancel_requested -> Worker 停止 -> cancelled`，前端等待最终 `end`
后再关闭当前 Run。

### RUN-ES-006 Durable terminal state

PostgreSQL `AgentRun.agent_status` 是终态事实来源。Redis `end` 只负责传输和唤醒；
缺少 Redis `end` 时仍能根据数据库状态结束 SSE。

### RUN-ES-007 Three-layer Run state

PostgreSQL 保存权威 Run，Pinia 保存当前运行态，`localStorage` 以
`active_run:{threadId}` 保存 Active Run 快照。创建 Run 和每个成功处理的 SSE event
都调用 `saveActiveRunSnapshot(threadId, runId, lastStreamId)` 覆盖写入快照；快照只保存
这三个字段，不保存消息、完整 event payload、Agent state 或渲染内容。页面刷新先向
后端核实 Run 状态；只有活跃 Run 才从 Redis Stream 起点重放。终态或无效快照必须
清除。

### RUN-ES-008 Frontend event projection

前端按外层 Run event type 解析并归并状态、Assistant 文本、Agent state 和
工具执行事件；不读取 Worker 内部 `chunk.status`，不建立平行的消息 DTO。

### RUN-ES-009 Output-aware activity indicator

`ChatLoadingStateComponent` 拥有等待状态的展示、经过时间和动画降级；
`ChatView` 拥有可见性。`Thinking` 只表示当前活跃 Run 尚未产生可见
Assistant 文本或 Agent tool 状态。当前 Run 一旦出现首个非空文本增量或首个
tool 消息，页面必须卸载该组件，不得同时展示 Assistant 文本、Agent tool 状态
和等待指示器。

## 12. Acceptance Criteria

- 创建 Run 后，Worker 在没有 SSE 客户端时仍继续执行。
- 创建响应包含后端 `AgentRun.run_type`；当前主链值为 `chat`。
- 运行期间 Pinia 持有完整运行态；创建 Run 和每个成功处理的 SSE event 都覆盖
  localStorage 中同一份 Active Run 快照。
- Active Run 快照只包含 `threadId/runId/lastStreamId`，不包含消息、完整 SSE payload、
  Agent state 或已渲染内容。
- 刷新后先核实 PostgreSQL Run 状态；活跃 Run 从 Redis Stream 起点重放，终态 Run
  直接读取 Thread Detail。
- 前端消费 `status/messages/custom/end`，不再只等待 `end`。
- 文本增量来自真实 `messages.items[].stream_event[]`。
- 当前 Run 尚无可见 Assistant 文本或 Agent tool 状态时，
  `ChatLoadingStateComponent` 显示 `Thinking`、3x3 像素波和经过时间；首个非空
  文本增量或首个 tool 消息渲染后立即卸载，且不受其他 Run 的消息影响。
- Thinking 与当前 Run 的 Agent tool 状态互斥；tool 状态可见期间不得重新显示
  Thinking。
- reduced motion 停止等待组件的像素和 shimmer 动画，但经过时间继续。
- 页面未刷新且 Pinia cursor 仍在内存时，SSE 续连同一个 Run 并从
  `Last-Stream-ID` 之后开始；整页刷新从 `0-0` 重放。
- 前端点击停止后显示 `cancel_requested`，直到收到 `cancelled` 终态。
- Redis 消息已经排空后才写入持久化终态。
- 页面收到终态后重新加载 PostgreSQL 历史消息。
- Redis Stream 过期或裁剪时以前端可重放窗口展示运行态，终态后以 PostgreSQL
  Thread Detail 收口。
- `startAgentRunStream()` 只编排快照保存、SSE 网络读取、事件解析与渲染三个职责。
- 终态、无效快照和登出都会清理对应的本地 Active Run 快照。
- 前端不创建、订阅或展示 SubAgent；本次实现不新增或修改 child Run 逻辑。
- 文档不包含模拟 ID、文本、工具参数或 payload。
- `git diff --check` 通过。
