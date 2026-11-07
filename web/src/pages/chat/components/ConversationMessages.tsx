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
  const active = current && props.active && !props.waiting
  const waiting = current && props.waiting

  // Only the last root-thread text stays outside the process; child output never becomes the answer.
  const last = row.messages.at(-1)
  const lastEvent = record(last?.payload.event)
  const hasAnswer =
    last?.payload.type === "text" &&
    typeof lastEvent.content === "string" &&
    Boolean(lastEvent.content.trim()) &&
    (!lastEvent.thread_id || lastEvent.thread_id === props.threadId)
  const process = hasAnswer ? row.messages.slice(0, -1) : row.messages
  const isProcessActive = active && !hasAnswer

  const artifacts = extractArtifactsFromMessages(row.messages, props.threadId)
  const label = waiting
    ? "Waiting for your response"
    : status === "failed"
      ? "Execution failed"
      : status === "cancelled"
        ? "Cancelled"
        : status === "interrupted"
          ? "Interrupted"
          : isProcessActive
            ? process.length
              ? "Working"
              : "Thinking"
            : "Execution process"

  const showProcess = process.length > 0 || isProcessActive || waiting

  return (
    <section className="grid min-w-0 gap-4" data-run-id={row.runId}>
      {showProcess && (
        <Thinking
          label={label}
          active={isProcessActive}
        >
          {process.length > 0 ? (
            <div className="flex min-w-0 flex-col gap-2">
              {process.map((message, index) => (
                <ChatMessage
                  key={`${record(message.payload.event).type ?? record(message.payload.event).name ?? message.payload.type}:${record(message.payload.event).tool_call_id ?? record(message.payload.event).message_id ?? index}`}
                  message={message}
                />
              ))}
            </div>
          ) : undefined}
        </Thinking>
      )}
      {hasAnswer && last && <ChatMessage message={last} />}
      {artifacts.length > 0 && <ArtifactList artifacts={artifacts} threadId={props.threadId} />}
    </section>
  )
}
