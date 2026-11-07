import type {
  ChatMessage as ChatMessageType,
  ChatRenderItem,
} from "@/pages/chat/types"
import { HumanMessageSection } from "./messages/HumanMessageSection"
import { AgentMarkdownSection } from "./messages/AgentMarkdownSection"
import { AgentReasoningSection } from "./messages/AgentReasoningSection"
import { AgentTasksSection } from "./messages/AgentTasksSection"
import { AgentRunSection } from "./messages/AgentRunSection"
import { ToolCall } from "./ToolCall"
import type { ThreadMessageAttachmentResponse } from "@/api/attachment"

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null

const isAttachment = (
  value: unknown,
): value is ThreadMessageAttachmentResponse =>
  isRecord(value) && typeof value.file_id === "string"

interface ChatMessageProps {
  item?: ChatRenderItem
  message?: ChatMessageType
}

export function ChatMessage({ item, message }: ChatMessageProps) {
  if (item) {
    if (item.kind === "human") {
      return (
        <HumanMessageSection
          content={item.content}
          attachments={item.attachments}
        />
      )
    }
    return <AgentRunSection item={item} />
  }

  if (!message) return null

  const event = isRecord(message.payload.event) ? message.payload.event : {}
  const content = typeof event.content === "string" ? event.content : ""
  const attachments = Array.isArray(event.attachments)
    ? event.attachments.filter(isAttachment)
    : []

  if (message.type === "human") {
    return (
      <HumanMessageSection
        content={content}
        attachments={attachments}
      />
    )
  }

  if (message.payload.type === "tool") {
    if (event.type === "tool_call") {
      return <ToolCall event={event} />
    }
    if (event.type === "reasoning") {
      return <AgentReasoningSection content={content} />
    }
    const state = isRecord(event.agent_state) ? event.agent_state : {}
    const todos = Array.isArray(state.agent_todo)
      ? state.agent_todo.filter(
          (todo): todo is { content: string; status: "pending" | "in_progress" | "completed" } =>
            isRecord(todo) &&
            typeof todo.content === "string" &&
            ["pending", "in_progress", "completed"].includes(String(todo.status)),
        )
      : []
    return <AgentTasksSection todos={todos} />
  }

  return (
    <AgentMarkdownSection
      content={content}
      attachments={attachments}
    />
  )
}
