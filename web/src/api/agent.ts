import { apiClient } from "@/api/client"
import type { UploadedAttachmentResponse } from "@/types/attachment"
import type {
  AgentRunCancelResponse,
  AgentRunCreateResponse,
  AgentRunEndEvent,
  AgentRunResumeRequest,
  AgentRunResumeResponse,
  AgentRunStreamEvent,
  AgentSummary,
  ThreadDetailResponse,
  ThreadListResponse,
  ThreadResponse
} from "@/types/chat"

export const listChatAgents = () =>
  apiClient.apiGet<AgentSummary[]>("/api/chat/agents", {
    requiresAuth: true
  })

export const listThreads = (
  options?: { query?: string; cursor?: string; limit?: number }
) => {
  const params = new URLSearchParams()
  if (options?.query) params.set("q", options.query)
  if (options?.cursor) params.set("cursor", options.cursor)
  if (options?.limit) params.set("limit", String(options.limit))
  const queryString = params.toString()
  const path = queryString
    ? `/api/chat/thread?${queryString}`
    : "/api/chat/thread"
  return apiClient.apiGet<ThreadListResponse>(path, {
    requiresAuth: true
  })
}

export const createThread = (agentId: string) =>
  apiClient.apiPost<ThreadResponse, { agent_id: string }>(
    "/api/chat/thread",
    { agent_id: agentId },
    { requiresAuth: true }
  )

export const getThreadDetail = (threadId: string) =>
  apiClient.apiGet<ThreadDetailResponse>(
    `/api/chat/thread/${encodeURIComponent(threadId)}`,
    { requiresAuth: true }
  )

export const uploadChatAttachments = (files: File[]) => {
  const body = new FormData()
  files.forEach((file) => body.append("files", file, file.name))
  return apiClient.apiPost<UploadedAttachmentResponse[], FormData>(
    "/api/chat/attachment/upload",
    body,
    { requiresAuth: true }
  )
}

export const createAgentRun = (
  query: string,
  agentId: string,
  threadId: string,
  attachmentFileIds: string[],
  modelId?: string
) =>
  apiClient.apiPost<AgentRunCreateResponse, Record<string, unknown>>(
    "/api/agent/runs",
    {
      query,
      agent_id: agentId,
      thread_id: threadId,
      thread_metadata: modelId ? { model: modelId } : {},
      msg_metadata: {
        attachment_file_ids: attachmentFileIds
      }
    },
    { requiresAuth: true }
  )

export const buildAgentRunStreamUrl = (runId: string, threadId: string) =>
  `/api/agent/runs/${encodeURIComponent(runId)}/events?thread_id=${encodeURIComponent(threadId)}`

// FIXEME: 父 Run 仅用于定位恢复点，响应会返回新的 Resume Run ID。
export const resumeAgentRun = (
  parentRunId: string,
  request: AgentRunResumeRequest
) =>
  apiClient.apiPost<AgentRunResumeResponse, AgentRunResumeRequest>(
    `/api/agent/runs/${encodeURIComponent(parentRunId)}/resume`,
    request,
    { requiresAuth: true }
  )

const readSseBlock = (block: string): AgentRunStreamEvent | null => {
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
    id: idLine ? idLine.slice(3).trimStart() : ""
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
        const event = readSseBlock(block)
        if (event?.type === "end") return event as AgentRunEndEvent
        if (event) await onEvent?.(event)
        separator = buffer.match(/\r?\n\r?\n/)
      }

      if (done) break
    }
  } finally {
    reader.releaseLock()
  }
  throw new Error("Agent Run 事件流在终态前结束")
}

export const cancelAgentRun = (runId: string) =>
  apiClient.apiPost<AgentRunCancelResponse>(
    `/api/agent/runs/${encodeURIComponent(runId)}/cancel`,
    undefined,
    { requiresAuth: true }
  )
