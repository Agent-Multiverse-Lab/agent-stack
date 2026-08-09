import type {
  AgentRunCancelResponse,
  AgentRunCreateResponse,
  AgentRunEndEvent,
  AgentSummary,
  ThreadDetailResponse,
  ThreadResponse
} from "@/types/chat"
import type { UploadedAttachmentResponse } from "@/types/attachment"

const readError = async (response: Response) => {
  const payload = (await response.json().catch(() => null)) as {
    detail?: unknown
  } | null
  return typeof payload?.detail === "string"
    ? payload.detail
    : `请求失败（${response.status}）`
}

const authorizedFetch = async (
  path: string,
  accessToken: string,
  init: RequestInit = {}
) => {
  const headers = new Headers(init.headers)
  headers.set("Authorization", `Bearer ${accessToken}`)
  const response = await fetch(path, { ...init, headers })
  if (!response.ok) throw new Error(await readError(response))
  return response
}

const authorizedJson = async <T>(
  path: string,
  accessToken: string,
  init: RequestInit = {}
): Promise<T> => {
  const response = await authorizedFetch(path, accessToken, init)
  return response.json() as Promise<T>
}

const jsonPost = (payload: Record<string, unknown>): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(payload)
})

export const listChatAgents = (accessToken: string) =>
  authorizedJson<AgentSummary[]>("/api/chat/agents", accessToken)

export const createThread = (agentId: string, accessToken: string) =>
  authorizedJson<ThreadResponse>(
    "/api/chat/thread",
    accessToken,
    jsonPost({ agent_id: agentId })
  )

export const getThreadDetail = (threadId: string, accessToken: string) =>
  authorizedJson<ThreadDetailResponse>(
    `/api/chat/thread/${encodeURIComponent(threadId)}`,
    accessToken
  )

export const uploadChatAttachments = (
  files: File[],
  accessToken: string
) => {
  const body = new FormData()
  files.forEach((file) => body.append("files", file, file.name))
  return authorizedJson<UploadedAttachmentResponse[]>(
    "/api/chat/attachment/upload",
    accessToken,
    { method: "POST", body }
  )
}

export const createAgentRun = (
  query: string,
  agentId: string,
  threadId: string,
  attachmentFileIds: string[],
  accessToken: string
) =>
  authorizedJson<AgentRunCreateResponse>(
    "/api/agent/runs",
    accessToken,
    jsonPost({
      query,
      agent_id: agentId,
      thread_id: threadId,
      msg_metadata: {
        attachment_file_ids: attachmentFileIds
      }
    })
  )

const readSseBlock = (block: string): AgentRunEndEvent | null => {
  const data = block
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n")
  if (!data) return null

  const event = JSON.parse(data) as { type?: unknown }
  return event.type === "end" ? (event as AgentRunEndEvent) : null
}

export const waitForAgentRunEnd = async (
  streamUrl: string,
  accessToken: string,
  signal: AbortSignal
): Promise<AgentRunEndEvent> => {
  const response = await authorizedFetch(streamUrl, accessToken, {
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
        const endEvent = readSseBlock(block)
        if (endEvent) return endEvent
        separator = buffer.match(/\r?\n\r?\n/)
      }

      if (done) break
    }
  } finally {
    reader.releaseLock()
  }
  throw new Error("Agent Run 事件流在终态前结束")
}

export const cancelAgentRun = (runId: string, accessToken: string) =>
  authorizedJson<AgentRunCancelResponse>(
    `/api/agent/runs/${encodeURIComponent(runId)}/cancel`,
    accessToken,
    { method: "POST" }
  )
