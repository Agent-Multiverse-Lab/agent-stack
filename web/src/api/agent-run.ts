import { apiClient } from "@/api/client"
import i18n from "@/i18n"

export interface ThreadRunMetadataResponse {
  run_id: string
  run_type: string
  status: string
  parent_run_id: string | null
  metadata: Record<string, unknown>
  started_at: string | null
  finished_at: string | null
}

export interface HumanQuestionResponse {
  question_id: string
  question: string
  options: { label: string; value: string }[]
}

export interface InteractionRequiredResponse {
  name: "ask_user"
  parent_run_id: string
  questions: HumanQuestionResponse[]
}

export interface AgentRunCreateRequest {
  query: string
  agent_id: string
  thread_id: string
  thread_metadata: Record<string, unknown>
  msg_metadata: {
    attachment_file_ids: string[]
  }
}

export interface AgentRunCreateResponse {
  run_id: string
  thread_id: string
  status: string
  request_id: string | null
  stream_url: string
}

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

export interface AgentRunStreamEvent extends Record<string, unknown> {
  id: string
  scope: "agent_run"
  type: string
  run_id: string
  thread_id: string | null
  created_at: string | null
}

export interface AgentRunMessagesItemResponse {
  request_id?: string | null
  response?: string | null
  thread_id?: string | null
  status?: "loading" | null
  stream_event: unknown[]
  metadata?: Record<string, unknown> | null
}

export interface AgentRunMessagesEvent extends AgentRunStreamEvent {
  type: "messages"
  items: AgentRunMessagesItemResponse[]
}

export interface AgentRunEndEvent extends AgentRunStreamEvent {
  type: "end"
  status: "completed" | "failed" | "cancelled" | "interrupted"
  error?: string
}

export const createAgentRun = (
  query: string,
  agentId: string,
  threadId: string,
  attachmentFileIds: string[],
  modelId?: string
) =>
  apiClient.apiPost<AgentRunCreateResponse, AgentRunCreateRequest>(
    "/api/agent/runs",
    {
      query,
      agent_id: agentId,
      thread_id: threadId,
      thread_metadata: modelId ? { model: modelId } : {},
      msg_metadata: {
        attachment_file_ids: attachmentFileIds,
      },
    },
    { requiresAuth: true }
  )

export const buildAgentRunStreamUrl = (runId: string, threadId: string) =>
  `/api/agent/runs/${encodeURIComponent(runId)}/events?thread_id=${encodeURIComponent(threadId)}`

// The parent Run locates the checkpoint; the response returns a new Resume Run ID.
export const resumeAgentRun = (
  parentRunId: string,
  request: AgentRunResumeRequest
) =>
  apiClient.apiPost<AgentRunResumeResponse, AgentRunResumeRequest>(
    `/api/agent/runs/${encodeURIComponent(parentRunId)}/resume`,
    request,
    { requiresAuth: true }
  )

const readSSEBlock = (block: string): AgentRunStreamEvent | null => {
  const lines = block.split(/\r?\n/)
  const data = lines
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n")
  if (!data) return null

  const event = JSON.parse(data) as unknown
  if (
    typeof event !== "object" ||
    event === null ||
    typeof (event as { type?: unknown }).type !== "string"
  ) {
    return null
  }

  const idLine = lines.find((line) => line.startsWith("id:"))
  return {
    ...event,
    id: idLine ? idLine.slice(3).trimStart() : "",
  } as AgentRunStreamEvent
}

export const consumeAgentRunStream = async (
  streamUrl: string,
  signal: AbortSignal,
  onEvent?: (event: AgentRunStreamEvent) => void | Promise<void>
): Promise<AgentRunEndEvent> => {
  const response = await apiClient.apiFetch(streamUrl, {
    requiresAuth: true,
    method: "GET",
    cache: "no-store",
    signal,
  })
  if (!response.body) throw new Error(i18n.t("Agent Run event stream is unreadable"))

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
        const event = readSSEBlock(block)
        if (event?.type === "end") return event as AgentRunEndEvent
        if (event) await onEvent?.(event)
        separator = buffer.match(/\r?\n\r?\n/)
      }

      if (done) break
    }
  } finally {
    reader.releaseLock()
  }
  throw new Error(i18n.t("Agent Run event stream ended before a terminal status"))
}

export const cancelAgentRun = (runId: string) =>
  apiClient.apiPost<AgentRunCancelResponse>(
    `/api/agent/runs/${encodeURIComponent(runId)}/cancel`,
    undefined,
    { requiresAuth: true }
  )
