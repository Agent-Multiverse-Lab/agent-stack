import type {
  AgentContentBlock,
  AgentTodoItem,
  ChatMessage as Message,
  ChatRenderItem,
  JsonValue,
  MarkdownBlock,
  ToolCallArguments,
  ToolCallBlock,
  ToolExecutionStatus,
} from "@/pages/chat/types"
import { extractArtifactsFromMessages } from "@/pages/chat/artifacts"
import type { ThreadMessageAttachmentResponse } from "@/api/attachment"

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null

const statusLabels: Record<string, ToolExecutionStatus> = {
  pending: "pending",
  running: "running",
  completed: "completed",
  error: "error",
  cancelled: "cancelled",
  interrupted: "interrupted",
  stopped: "stopped",
}

const isToolExecutionStatus = (value: unknown): value is ToolExecutionStatus =>
  typeof value === "string" && Object.prototype.hasOwnProperty.call(statusLabels, value)

function formatValue(value: unknown): string {
  if (typeof value === "string") return value
  return JSON.stringify(value, null, 2) ?? String(value)
}

function parseTimestamp(value: unknown): number | null {
  const result = typeof value === "string" ? Date.parse(value) : NaN
  return Number.isFinite(result) ? result : null
}

function extractMessageId(event: Record<string, unknown>, fallback: string): string | number {
  if (typeof event.message_id === "string" || typeof event.message_id === "number") {
    return event.message_id
  }
  return fallback
}

function extractRunId(message: Message): string | null {
  const event = isRecord(message.payload.event) ? message.payload.event : {}
  const runObj = isRecord(event.run) ? event.run : null
  const id = event.run_id ?? runObj?.run_id
  return typeof id === "string" ? id : null
}

function toContentBlock(message: Message, indexFallback: number): AgentContentBlock {
  const event = isRecord(message.payload.event) ? message.payload.event : {}
  const messageId = extractMessageId(event, `block-${indexFallback}`)
  const content = typeof event.content === "string" ? event.content : ""
  const attachments = Array.isArray(event.attachments)
    ? (event.attachments.filter(
        (item): item is ThreadMessageAttachmentResponse =>
          isRecord(item) && typeof item.file_id === "string",
      ) as ThreadMessageAttachmentResponse[])
    : []

  if (message.payload.type === "tool") {
    if (event.type === "tool_call") {
      const receivedStatus = String(event.status ?? "pending")
      const status: ToolExecutionStatus = isToolExecutionStatus(receivedStatus)
        ? receivedStatus
        : "pending"
      const name = typeof event.name === "string" ? event.name : "Tool"
      const toolCallId =
        typeof event.tool_call_id === "string"
          ? event.tool_call_id
          : typeof event.activity_id === "string"
            ? event.activity_id
            : String(messageId)
      const output =
        isRecord(event.output) && "content" in event.output
          ? (event.output.content as JsonValue)
          : (event.output as JsonValue)
      const progress = Array.isArray(event.output_deltas)
        ? event.output_deltas.map(formatValue).join("")
        : undefined

      const toolBlock: ToolCallBlock = {
        kind: "tool_call",
        messageId,
        toolCallId,
        name,
        status,
        index: typeof event.index === "number" ? event.index : undefined,
        args: event.args as ToolCallArguments,
        output,
        progress: progress || undefined,
        error: typeof event.error === "string" ? event.error : undefined,
      }
      return toolBlock
    }

    if (event.type === "reasoning") {
      return {
        kind: "reasoning",
        messageId,
        content,
      }
    }

    const state = isRecord(event.agent_state) ? event.agent_state : {}
    const todos: AgentTodoItem[] = Array.isArray(state.agent_todo)
      ? (state.agent_todo.filter(
          (item): item is AgentTodoItem =>
            isRecord(item) &&
            typeof item.content === "string" &&
            ["pending", "in_progress", "completed"].includes(String(item.status)),
        ) as AgentTodoItem[])
      : []

    return {
      kind: "agent_tasks",
      messageId,
      todos,
    }
  }

  return {
    kind: "markdown",
    messageId,
    content,
    attachments,
  }
}

interface RunGroup {
  runId: string
  messages: Message[]
}

interface BuildOptions {
  threadId?: string
  currentRunId?: string | null
  status?: string | null
  active?: boolean
  waiting?: boolean
  startedAt?: number | null
}

export function buildChatRenderItems(
  messages: Message[],
  options: BuildOptions = {},
): ChatRenderItem[] {
  const items: ChatRenderItem[] = []
  const runGroups = new Map<string, RunGroup>()
  const runOrder: string[] = []
  const positions = new Map<string, number>()

  let messageCounter = 0
  for (const message of messages) {
    messageCounter += 1
    const event = isRecord(message.payload.event) ? message.payload.event : {}
    const messageId = extractMessageId(event, `msg-${messageCounter}`)

    if (message.type === "human") {
      positions.set(`human-${messageId}`, messageCounter)
      const content = typeof event.content === "string" ? event.content : ""
      const attachments = Array.isArray(event.attachments)
        ? (event.attachments.filter(
            (item): item is ThreadMessageAttachmentResponse =>
              isRecord(item) && typeof item.file_id === "string",
          ) as ThreadMessageAttachmentResponse[])
        : []

      items.push({
        kind: "human",
        key: `human-${messageId}`,
        messageId,
        content,
        attachments,
      })
      continue
    }

    const runId = extractRunId(message) ?? (options.currentRunId || `fallback-run-${messageCounter}`)
    let group = runGroups.get(runId)
    if (!group) {
      group = { runId, messages: [] }
      runGroups.set(runId, group)
      runOrder.push(runId)
      positions.set(runId, messageCounter)
    }
    group.messages.push(message)
  }

  // Ensure active/waiting current run exists even before any message chunks arrive
  if (
    options.currentRunId &&
    (options.active || options.waiting) &&
    !runGroups.has(options.currentRunId)
  ) {
    runGroups.set(options.currentRunId, { runId: options.currentRunId, messages: [] })
    runOrder.push(options.currentRunId)
  }

  for (const rId of runOrder) {
    const group = runGroups.get(rId)
    if (!group) continue

    const isCurrent = rId === options.currentRunId
    const metadata =
      group.messages
        .map((m) => (isRecord(m.payload.event) && isRecord(m.payload.event.run) ? m.payload.event.run : null))
        .find((r) => isRecord(r) && r.run_id === rId) ?? {}

    const status = isCurrent ? (options.status ?? null) : (typeof metadata.status === "string" ? metadata.status : null)
    const active = Boolean(isCurrent && options.active && !options.waiting)
    const waiting = Boolean(isCurrent && options.waiting)

    // Check if the last message is a main-thread answer text
    const last = group.messages.at(-1)
    const lastEvent = isRecord(last?.payload.event) ? last.payload.event : {}
    const hasAnswer =
      last?.payload.type === "text" &&
      typeof lastEvent.content === "string" &&
      Boolean(lastEvent.content.trim()) &&
      (!lastEvent.thread_id || lastEvent.thread_id === options.threadId)

    const processMessages = hasAnswer ? group.messages.slice(0, -1) : group.messages
    const processBlocks = processMessages.map((m, idx) => toContentBlock(m, idx))

    const answerBlock: MarkdownBlock | null = hasAnswer && last
      ? {
          kind: "markdown",
          messageId: extractMessageId(lastEvent, `ans-${rId}`),
          content: typeof lastEvent.content === "string" ? lastEvent.content : "",
          attachments: Array.isArray(lastEvent.attachments)
            ? (lastEvent.attachments.filter(
                (item): item is ThreadMessageAttachmentResponse =>
                  isRecord(item) && typeof item.file_id === "string",
              ) as ThreadMessageAttachmentResponse[])
            : [],
        }
      : null

    const startedAt = isCurrent
      ? (options.startedAt ?? null)
      : parseTimestamp(metadata.started_at)
    const finishedAt = parseTimestamp(metadata.finished_at)
    const answerCreatedAt = hasAnswer ? parseTimestamp(lastEvent.created_at) : null

    const artifacts = extractArtifactsFromMessages(group.messages, options.threadId)

    items.push({
      kind: "agent_run",
      key: rId,
      runId: rId,
      threadId: options.threadId,
      status,
      active,
      waiting,
      startedAt,
      finishedAt,
      answerCreatedAt,
      processBlocks,
      answerBlock,
      artifacts,
    })
  }

  return items.sort((a, b) =>
    (positions.get(a.key) ?? Infinity) - (positions.get(b.key) ?? Infinity),
  )
}
