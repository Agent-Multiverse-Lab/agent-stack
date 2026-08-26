import { computed, ref } from "vue"

import {
  buildAgentRunStreamUrl,
  cancelAgentRun,
  consumeAgentRunStream,
  createAgentRun
} from "@/api/agent"
import type {
  AgentRunStreamEvent,
  ThreadDetailResponse,
  ThreadRunMetadataResponse
} from "@/types/chat"

const activeRunStatuses = new Set([
  "pending",
  "running",
  "cancel_requested"
])

const isAgentRunActiveStatus = (status: string | null | undefined) =>
  status ? activeRunStatuses.has(status) : false

interface AgentRunCreateRequest {
  query: string
  agentId: string
  threadId: string
  attachmentFileIds: string[]
  modelId?: string
}

type RunMessageEventHandler = (
  event: AgentRunStreamEvent
) => void | Promise<void>

export const useAgentRun = () => {
  const runId = ref<string | null>(null)
  const runStatus = ref<string | null>(null)
  const streamUrl = ref<string | null>(null)
  const cancelling = ref(false)
  let runStateVersion = 0

  const isRunActive = computed(() =>
    isAgentRunActiveStatus(runStatus.value)
  )

  const createRun = async (request: AgentRunCreateRequest) => {
    const expectedVersion = ++runStateVersion
    const run = await createAgentRun(
      request.query,
      request.agentId,
      request.threadId,
      request.attachmentFileIds,
      request.modelId
    )
    if (runStateVersion !== expectedVersion) return run
    runId.value = run.run_id
    runStatus.value = run.status
    streamUrl.value = run.stream_url
    cancelling.value = false
    return run
  }

  const restoreRunFromThread = (
    detail: ThreadDetailResponse
  ): ThreadRunMetadataResponse | null => {
    runStateVersion += 1
    const latestRun = [...detail.messages]
      .reverse()
      .find((message) => message.run)?.run ?? null
    const activeRun = [...detail.messages]
      .reverse()
      .find(
        (message) =>
          message.run && isAgentRunActiveStatus(message.run.status)
      )?.run ?? null
    const restoredRun = activeRun ?? latestRun
    const nextRunId = restoredRun?.run_id ?? null
    if (runId.value !== nextRunId) cancelling.value = false
    runId.value = nextRunId
    runStatus.value = restoredRun?.status ?? null
    streamUrl.value = activeRun
      ? buildAgentRunStreamUrl(
          activeRun.run_id,
          detail.thread.thread_id
        )
      : null
    return activeRun
  }

  const consumeRunStream = async (
    signal: AbortSignal,
    onMessageEvent: RunMessageEventHandler
  ) => {
    const targetRunId = runId.value
    const targetStreamUrl = streamUrl.value
    if (!targetRunId || !targetStreamUrl || !isRunActive.value) return null

    const endEvent = await consumeAgentRunStream(
      targetStreamUrl,
      signal,
      async (event) => {
        if (runId.value !== targetRunId) return
        if (event.type === "status" && typeof event.status === "string") {
          runStatus.value = event.status
          return
        }
        await onMessageEvent(event)
      }
    )
    if (runId.value === targetRunId) {
      runStatus.value = endEvent.status
      streamUrl.value = null
    }
    return endEvent
  }

  const cancelCurrentRun = async () => {
    const targetRunId = runId.value
    if (!targetRunId || cancelling.value || !isRunActive.value) return

    cancelling.value = true
    try {
      const response = await cancelAgentRun(targetRunId)
      if (runId.value === targetRunId) runStatus.value = response.status
    } catch (caught) {
      if (runId.value === targetRunId) throw caught
    } finally {
      if (runId.value === targetRunId) cancelling.value = false
    }
  }

  const clearRun = () => {
    runStateVersion += 1
    runId.value = null
    runStatus.value = null
    streamUrl.value = null
    cancelling.value = false
  }

  return {
    runId,
    runStatus,
    streamUrl,
    cancelling,
    isRunActive,
    createRun,
    restoreRunFromThread,
    consumeRunStream,
    cancelCurrentRun,
    clearRun
  }
}
