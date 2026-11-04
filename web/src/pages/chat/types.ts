import type {
  ThreadMessageAttachmentResponse,
  UploadedAttachmentResponse,
} from "@/api/attachment"
import type {
  HumanQuestionResponse,
  InteractionRequiredResponse,
} from "@/api/agent-run"
import type { PresentedArtifact } from "@/pages/chat/artifacts"

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

export type AgentTodoStatus = "pending" | "in_progress" | "completed"

export interface AgentTodoItem {
  content: string
  status: AgentTodoStatus
}

export interface BaseContentBlock {
  messageId: string | number
}

export interface MarkdownBlock extends BaseContentBlock {
  kind: "markdown"
  content: string
  attachments: ThreadMessageAttachmentResponse[]
}

export interface ReasoningBlock extends BaseContentBlock {
  kind: "reasoning"
  content: string
}

export interface ToolCallBlock extends BaseContentBlock {
  kind: "tool_call"
  toolCallId: string
  name: string
  status: ToolExecutionStatus
  index?: number
  args?: ToolCallArguments
  output?: JsonValue
  progress?: string
  error?: string
}

export interface AgentTasksBlock extends BaseContentBlock {
  kind: "agent_tasks"
  todos: AgentTodoItem[]
}

export type AgentContentBlock =
  | MarkdownBlock
  | ReasoningBlock
  | ToolCallBlock
  | AgentTasksBlock

export type ChatRenderItem =
  | {
      kind: "human"
      key: string
      messageId: string | number
      content: string
      attachments: ThreadMessageAttachmentResponse[]
    }
  | {
      kind: "agent_run"
      key: string
      runId: string
      threadId?: string
      status: string | null
      active: boolean
      waiting: boolean
      startedAt: number | null
      finishedAt: number | null
      answerCreatedAt: number | null
      processBlocks: AgentContentBlock[]
      answerBlock: MarkdownBlock | null
      artifacts: PresentedArtifact[]
    }
