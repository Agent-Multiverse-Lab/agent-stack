import type {
  ThreadMessageAttachmentResponse,
  UploadedAttachmentResponse,
} from "@/api/attachment"
import type {
  HumanQuestionResponse,
  InteractionRequiredResponse,
} from "@/api/agent-run"

export type JsonPrimitive = string | number | boolean | null
export type JsonValue =
  | JsonPrimitive
  | JsonValue[]
  | { [key: string]: JsonValue }

export type ToolCallArguments = JsonValue

export type ToolExecutionStatus =
  | "pending"
  | "running"
  | "completed"
  | "error"
  | "cancelled"
  | "interrupted"
  | "stopped"

export interface AIMessageChunk {
  type: "tool_call"
  message_id: string
  thread_id?: string | null
  tool_call_id?: string | null
  name?: string | null
  args?: ToolCallArguments
  index?: number | null
}

export interface ChatMessagePayload extends Record<string, unknown> {
  type: "text" | "tool"
  event: unknown
}

export interface ChatMessage {
  type: "ai" | "human"
  payload: ChatMessagePayload
}

export type HumanQuestion = HumanQuestionResponse
export type InteractionRequired = InteractionRequiredResponse

export interface AgentRunCreateInput {
  query: string
  agentId: string
  threadId: string
  attachmentFileIds: string[]
  modelId?: string
}

export type ChatAttachment =
  | UploadedAttachmentResponse
  | ThreadMessageAttachmentResponse
