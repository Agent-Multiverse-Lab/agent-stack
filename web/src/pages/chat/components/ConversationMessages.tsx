import type { ChatMessage as Message } from "@/pages/chat/types"
import { extractArtifactsFromMessages } from "@/pages/chat/artifacts"
import { ArtifactList } from "./ArtifactCard"
import { ChatMessage } from "./ChatMessage"
import { Thinking } from "./Thinking"

const record = (value: unknown): Record<string, unknown> =>
  typeof value === "object" && value !== null ? (value as Record<string, unknown>) : {}

function runId(message: Message): string | null {
  const event = record(message.payload.event)
  const id = event.run_id ?? record(event.run).run_id
  return typeof id === "string" ? id : null
}

type Row = { key: string; runId: string | null; messages: Message[] }

export function groupRunMessages(messages: Message[]): Row[] {
  const rows: Row[] = []
  const runs = new Map<string, Row>()
  for (const [index, message] of messages.entries()) {
    const id = message.type === "ai" ? runId(message) : null
    if (!id) {
      rows.push({ key: `message-${index}`, runId: null, messages: [message] })
      continue
    }
    let row = runs.get(id)
    if (!row) {
      row = { key: id, runId: id, messages: [] }
      rows.push(row)
      runs.set(id, row)
    }
    row.messages.push(message)
  }
  return rows
}

type RunSegment =
  | { kind: "text"; key: string; message: Message }
  | { kind: "process"; key: string; messages: Message[] }

function messageKey(message: Message, index: number): string {
  const event = record(message.payload.event)
  return `${event.type ?? event.name ?? message.payload.type}:${event.tool_call_id ?? event.message_id ?? index}`
}

function isMainThreadText(message: Message, threadId: string | undefined): boolean {
  if (message.payload.type !== "text") return false
  const event = record(message.payload.event)
  const hasText = typeof event.content === "string" && Boolean(event.content.trim())
  const hasAttachments = Array.isArray(event.attachments) && event.attachments.length > 0
  if (!hasText && !hasAttachments) return false
  return !event.thread_id || !threadId || event.thread_id === threadId
}

function isEmptyText(message: Message): boolean {
  if (message.payload.type !== "text") return false
  const event = record(message.payload.event)
  const hasText = typeof event.content === "string" && Boolean(event.content.trim())
  const hasAttachments = Array.isArray(event.attachments) && event.attachments.length > 0
  return !hasText && !hasAttachments
}

export function segmentRunMessages(
  messages: Message[],
  threadId: string | undefined,
): RunSegment[] {
  const visibleMessages = messages.filter((message) => !isEmptyText(message))
  const lastMessage = visibleMessages.at(-1)
  const hasAnswer = Boolean(
    lastMessage && isMainThreadText(lastMessage, threadId),
  )
  const processMessages = hasAnswer
    ? visibleMessages.slice(0, -1)
    : visibleMessages
  const segments: RunSegment[] = []

  if (processMessages.length > 0) {
    segments.push({
      kind: "process",
      key: `process-${messageKey(processMessages[0], 0)}`,
      messages: processMessages,
    })
  }
  if (hasAnswer && lastMessage) {
    segments.push({
      kind: "text",
      key: messageKey(lastMessage, visibleMessages.length - 1),
      message: lastMessage,
    })
  }
  return segments
}

interface Props {
  messages: Message[]
  threadId: string | undefined
  currentRunId: string | null
  status: string | null
  active: boolean
  waiting: boolean
  startedAt?: number | null
}

export function ConversationMessages(props: Props) {
  const rows = groupRunMessages(props.messages)
  if (
    props.currentRunId &&
    (props.active || props.waiting) &&
    !rows.some((row) => row.runId === props.currentRunId)
  ) {
    rows.push({ key: props.currentRunId, runId: props.currentRunId, messages: [] })
  }
  return rows.map((row) =>
    row.runId ? (
      <RunMessages key={row.key} {...props} row={row} />
    ) : (
      <ChatMessage key={row.key} message={row.messages[0]} />
    ),
  )
}

function RunMessages({ row, ...props }: Props & { row: Row }) {
  const current = row.runId === props.currentRunId
  const metadata =
    row.messages
      .map((message) => record(record(message.payload.event).run))
      .find((run) => run.run_id === row.runId) ?? {}
  const status = current ? props.status : metadata.status
  const active = Boolean(current && props.active && !props.waiting)
  const waiting = Boolean(current && props.waiting)

  const segments = segmentRunMessages(row.messages, props.threadId)
  const artifacts = extractArtifactsFromMessages(row.messages, props.threadId)

  const terminalStatusLabel = waiting
    ? "Waiting for your response"
    : status === "failed"
      ? "Execution failed"
      : status === "cancelled"
        ? "Cancelled"
        : status === "interrupted"
          ? "Interrupted"
          : null

  const showTrailingThinking =
    (segments.length === 0 && (active || Boolean(terminalStatusLabel))) ||
    (segments.length > 0 && Boolean(terminalStatusLabel) && segments.at(-1)?.kind !== "process")

  return (
    <section className="grid min-w-0 gap-4" data-run-id={row.runId}>
      {segments.map((segment, segIndex) => {
        const isLastSegment = segIndex === segments.length - 1
        if (segment.kind === "text") {
          return <ChatMessage key={segment.key} message={segment.message} />
        }
        const isProcessActive = active && isLastSegment
        const processLabel =
          isLastSegment && terminalStatusLabel
            ? terminalStatusLabel
            : isProcessActive
              ? "Working"
              : "Execution process"
        return (
          <Thinking
            key={segment.key}
            label={processLabel}
            active={isProcessActive}
          >
            <div className="flex min-w-0 flex-col gap-2">
              {segment.messages.map((message, index) => (
                <ChatMessage
                  key={messageKey(message, index)}
                  message={message}
                />
              ))}
            </div>
          </Thinking>
        )
      })}
      {showTrailingThinking && (
        <Thinking
          label={terminalStatusLabel ?? "Thinking"}
          active={active && !terminalStatusLabel}
        />
      )}
      {artifacts.length > 0 && <ArtifactList artifacts={artifacts} threadId={props.threadId} />}
    </section>
  )
}
