import { apiClient } from "@/api/client"
import i18n from "@/i18n"

export interface ThreadRunMetadataResponse {
  run_id: string
  run_type: string
  status: string
  created_by_run_id: string | null
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
  created_by_run_id: string
  questions: HumanQuestionResponse[]
}

export interface AgentRunCreateRequest {
  query?: string | null
  agent_id: string
  thread_id: string
  request_metadata: {
    type: "chat" | "resume"
    model?: string
    request_id?: string
    attachment_file_ids?: string[]
    resume?: { answers: Record<string, string> }
  }
  image_content?: string | null
}

export interface AgentRunCreateResponse {
  run_id: string
  thread_id: string
  status: string
  request_id: string | null
  stream_url: string
}

export interface AgentRunResumeResponse extends AgentRunCreateResponse {
  run_type: "resume"
  created_by_run_id: string
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

/**
 * 提交普通对话输入，将模型和附件 ID 合并到 request_metadata，并标记 type 为 chat。
 * @param query 用户输入的正文；仅发送附件时可为空字符串。
 * @param agentId 当前会话绑定的 Agent 标识。
 * @param threadId 已创建的会话 ID。
 * @param attachmentFileIds 上传接口返回的附件 file_id 列表。
 * @param modelId 所选模型的 provider_id/model_id；省略时由后端解析会话模型。
 * @returns Run 标识、当前状态、请求 ID 和用于订阅执行事件的 stream_url。
 */
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
      request_metadata: {
        type: "chat",
        ...(modelId ? { model: modelId } : {}),
        attachment_file_ids: attachmentFileIds,
      },
    },
    { requiresAuth: true }
  )

/**
 * 根据会话详情中的 Run ID 和会话 ID，重建已有 Run 的 SSE 订阅地址。
 * @param runId Run 唯一标识。
 * @param threadId 所属会话 ID。
 * @returns 用于订阅该 Run 事件流的请求路径。
 */
export const buildAgentRunStreamUrl = (runId: string, threadId: string) =>
  `/api/agent/runs/${encodeURIComponent(runId)}/events?thread_id=${encodeURIComponent(threadId)}`

/**
 * 提交 Agent 提问的回答，创建新的 Resume Run 继续父 Run 的 checkpoint。
 * @param createdByRunId 待回答交互中的父 Run ID，用于定位恢复入口。
 * @param request 共用创建请求；request_metadata.type 为 resume，resume.answers 保存
 * question_id 到选项 value 的映射，request_id 用于同一回答请求的幂等重试。
 * @returns 新 Resume Run 的 ID、父 Run ID 和新的 stream_url。
 */
export const resumeAgentRun = (
  createdByRunId: string,
  request: AgentRunCreateRequest
) =>
  apiClient.apiPost<AgentRunResumeResponse, AgentRunCreateRequest>(
    `/api/agent/runs/${encodeURIComponent(createdByRunId)}/resume`,
    request,
    { requiresAuth: true }
  )

/**
 * 解析完整 SSE 数据块并提取事件 ID；缺少 data 或 type 时返回 null，非法 JSON 抛出异常。
 * @param block 以空行分隔的单个 SSE 文本块。
 * @returns 解析后的事件对象，无效事件返回 null。
 */
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

/**
 * 读取 Run 的 SSE 响应，将网络分块拼成完整事件后逐条处理。
 * @param streamUrl 创建、恢复接口返回或根据会话详情重建的订阅地址。
 * @param signal 用于中断当前订阅；中断连接不会取消后端 Run。
 * @param onEvent 非 end 事件的处理函数；等待其完成后再处理下一条事件。
 * @returns end 终态事件，由调用方处理；连接提前结束或读取失败时抛出异常。
 */
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

/**
 * 请求取消指定 Run，返回后端当前状态；cancel_requested 仍需等待最终取消结果。
 * @param runId 需要取消的 Run 唯一标识。
 * @returns 取消请求后的 Run 状态信息。
 */
export const cancelAgentRun = (runId: string) =>
  apiClient.apiPost<AgentRunCancelResponse>(
    `/api/agent/runs/${encodeURIComponent(runId)}/cancel`,
    undefined,
    { requiresAuth: true }
  )
