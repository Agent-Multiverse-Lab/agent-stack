import type { ThreadMessageAttachmentResponse } from "@/types/attachment"

export type JsonObject = Record<string, unknown>
export type IsoDateTime = string

export type AgentToolStatus = "running" | "completed" | "failed"

export type AgentToolState = JsonObject & {
  status: AgentToolStatus
}

export interface AgentTool {
  name: string
  state: AgentToolState
}

export interface AgentSummary {
  id: string
  name: string
  description: string
}

export interface ThreadResponse {
  uid: string
  title: string
  thread_id: string
  agent_id: string
  created_at: IsoDateTime
  updated_at: IsoDateTime
  metadata: JsonObject
}

export interface ThreadSummaryResponse {
  thread_id: string
  title: string
  summary: string | null
  agent_id: string
  metadata: JsonObject
  created_at: IsoDateTime
  updated_at: IsoDateTime
  last_message_at: IsoDateTime | null
}

export interface ThreadRunMetadataResponse {
  run_id: string
  run_type: string
  status: string
  parent_run_id: string | null
  metadata: JsonObject
  started_at: IsoDateTime | null
  finished_at: IsoDateTime | null
}

export interface ThreadMessageResponse {
  message_id: number
  role: string
  content: string
  image_content: string | null
  message_type: string
  status: string
  request_id: string | null
  run: ThreadRunMetadataResponse | null
  attachments: ThreadMessageAttachmentResponse[]
  created_at: IsoDateTime
  updated_at: IsoDateTime
}

export interface ThreadDetailResponse {
  thread: ThreadSummaryResponse
  messages: ThreadMessageResponse[]
  next_before_message_id: number | null
}

export interface AgentRunCreateResponse {
  run_id: string
  thread_id: string
  status: string
  request_id: string | null
  stream_url: string
}

export interface AgentRunCancelResponse {
  run_id: string
  thread_id: string
  agent_id: string
  status: string
}

export interface AgentRunStreamEvent extends JsonObject {
  id: string
  scope: "agent_run"
  type: string
  run_id: string
  thread_id: string | null
  created_at: IsoDateTime | null
}

export interface AgentRunEndEvent extends AgentRunStreamEvent {
  type: "end"
  status: "completed" | "failed" | "cancelled"
  error?: string
}

export interface ChatMessagePayload extends JsonObject {
  type: "text" | "tool"
  event: unknown
}

export interface ChatMessage {
  type: "ai" | "human"
  payload: ChatMessagePayload
}

export interface ThreadListResponse {
  items: ThreadSummaryResponse[]
  next_cursor: string | null
  has_more: boolean
}
