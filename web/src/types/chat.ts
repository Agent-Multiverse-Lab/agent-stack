import type { Agent } from "@/types/agent"
import type { ThreadMessageAttachmentResponse } from "@/types/attachment"

export type JsonObject = Record<string, unknown>
export type IsoDateTime = string

export interface AgentCatalogResponse {
  agents: Agent[]
  subagents: Agent[]
}

export interface AgentContextConfiguration {
  system_prompt: string
  model: string
  summary_threshold: number
  summary_keep_messages: number
  summary_prompt: string
  summary_tool_result_token_limit: number
  tools: unknown[]
  mcps: string[]
  skill_root: string | null
  style_profolio: Record<string, unknown>
}

export interface AgentUpdateRequest {
  name?: string
  description?: string
  enabled?: boolean
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

export interface HumanQuestion {
  question_id: string
  question: string
  options: { label: string; value: string }[]
}

export interface InteractionRequired {
  name: "ask_user"
  parent_run_id: string
  questions: HumanQuestion[]
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
  active_run: ThreadRunMetadataResponse | null
  pending_interaction: InteractionRequired | null
}

export interface AgentRunCreateResponse {
  run_id: string
  thread_id: string
  status: string
  request_id: string | null
  stream_url: string
}

// 回答按 question_id 对应选项 value，幂等键属于本次恢复请求。
export interface AgentRunResumeRequest {
  thread_id: string
  thread_metadata: {
    request_id: string
    resume: {
      answers: Record<string, string>
    }
  }
}

export interface AgentRunResumeResponse extends AgentRunCreateResponse {
  run_type: "resume"
  parent_run_id: string
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
  status: "completed" | "failed" | "cancelled" | "interrupted"
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
