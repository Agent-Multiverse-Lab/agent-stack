import { computed, ref } from "vue"

import {
  cancelAgentRun,
  createAgentRun,
  createThread,
  getThreadDetail,
  listChatAgents,
  uploadChatAttachments,
  waitForAgentRunEnd
} from "@/api/chat"
import { useAuthStore } from "@/stores/useAuthStore"
import type { UploadedAttachmentResponse } from "@/types/attachment"
import type {
  AgentRunEndEvent,
  ThreadMessageResponse,
  ThreadSummaryResponse
} from "@/types/chat"

type ThreadCreatedHandler = (threadId: string) => void | Promise<void>

const activeRunStatuses = new Set(["pending", "running", "cancel_requested"])

const errorText = (error: unknown) =>
  error instanceof Error ? error.message : "请求失败"

const isAbortError = (error: unknown) =>
  error instanceof DOMException && error.name === "AbortError"

const runStreamUrl = (runId: string, threadId: string) =>
  `/api/agent/runs/${encodeURIComponent(runId)}/events?thread_id=${encodeURIComponent(threadId)}`

export const useChat = () => {
  const authStore = useAuthStore()
  const thread = ref<ThreadSummaryResponse | null>(null)
  const messages = ref<ThreadMessageResponse[]>([])
  const draft = ref("")
  const attachments = ref<UploadedAttachmentResponse[]>([])
  const uploadingCount = ref(0)
  const uploadError = ref("")
  const runId = ref<string | null>(null)
  const runStatus = ref<string | null>(null)
  const streamUrl = ref<string | null>(null)
  const loading = ref(false)
  const submitting = ref(false)
  const cancelling = ref(false)
  const error = ref("")

  let streamController: AbortController | null = null
  let operation = 0
  let uploadGeneration = 0
  let optimisticMessageId = -1

  const isRunActive = computed(() =>
    runStatus.value ? activeRunStatuses.has(runStatus.value) : false
  )

  const requireAccessToken = () => {
    if (!authStore.accessToken) throw new Error("请先登录后再开始对话")
    return authStore.accessToken
  }

  const abortStream = () => {
    streamController?.abort()
    streamController = null
  }

  const clearRun = () => {
    abortStream()
    runId.value = null
    runStatus.value = null
    streamUrl.value = null
    submitting.value = false
    cancelling.value = false
  }

  const clearPendingInput = () => {
    uploadGeneration += 1
    draft.value = ""
    attachments.value = []
    uploadingCount.value = 0
    uploadError.value = ""
  }

  const applyThreadDetail = async (
    threadId: string,
    accessToken: string,
    expectedOperation: number
  ) => {
    const detail = await getThreadDetail(threadId, accessToken)
    if (operation !== expectedOperation) return false
    thread.value = detail.thread
    messages.value = detail.messages
    const latestRun = [...detail.messages]
      .reverse()
      .find((message) => message.run)?.run ?? null
    const activeRun = [...detail.messages]
      .reverse()
      .find(
        (message) =>
          message.run && activeRunStatuses.has(message.run.status)
      )?.run ?? null
    runId.value = activeRun?.run_id ?? latestRun?.run_id ?? null
    runStatus.value = activeRun?.status ?? latestRun?.status ?? null
    streamUrl.value = activeRun
      ? runStreamUrl(activeRun.run_id, threadId)
      : null
    return true
  }

  const monitorRun = async (
    threadId: string,
    accessToken: string,
    expectedOperation: number
  ) => {
    const monitoredRunId = runId.value
    if (!monitoredRunId || !streamUrl.value || !isRunActive.value) return

    while (
      operation === expectedOperation &&
      runId.value === monitoredRunId &&
      streamUrl.value &&
      isRunActive.value
    ) {
      const controller = new AbortController()
      streamController = controller
      let endEvent: AgentRunEndEvent
      try {
        endEvent = await waitForAgentRunEnd(
          streamUrl.value,
          accessToken,
          controller.signal
        )
      } catch (caught) {
        if (operation !== expectedOperation || isAbortError(caught)) return
        error.value = errorText(caught)
        try {
          await applyThreadDetail(
            threadId,
            accessToken,
            expectedOperation
          )
        } catch {
          // 保持已知 Run 状态，稍后重新连接。
        }
        if (
          operation !== expectedOperation ||
          runId.value !== monitoredRunId
        ) {
          return
        }
        if (!isRunActive.value) {
          error.value = runStatus.value === "failed"
            ? "Agent 执行失败"
            : ""
          return
        }
        await new Promise((resolve) => window.setTimeout(resolve, 1000))
        continue
      } finally {
        if (streamController === controller) streamController = null
      }

      if (operation !== expectedOperation) return
      runStatus.value = endEvent.status
      error.value = ""
      try {
        await applyThreadDetail(
          threadId,
          accessToken,
          expectedOperation
        )
      } catch (caught) {
        if (operation === expectedOperation && !isAbortError(caught)) {
          error.value = errorText(caught)
        }
      }
      if (operation !== expectedOperation) return
      if (endEvent.status === "failed") {
        error.value = endEvent.error || "Agent 执行失败"
      }
      return
    }
  }

  const resetThread = () => {
    operation += 1
    clearRun()
    thread.value = null
    messages.value = []
    clearPendingInput()
    error.value = ""
    loading.value = false
  }

  const loadThread = async (threadId: string) => {
    const expectedOperation = ++operation
    clearRun()
    clearPendingInput()
    thread.value = null
    messages.value = []
    loading.value = true
    error.value = ""
    try {
      const accessToken = requireAccessToken()
      const applied = await applyThreadDetail(
        threadId,
        accessToken,
        expectedOperation
      )
      if (applied && isRunActive.value) {
        void monitorRun(threadId, accessToken, expectedOperation)
      }
    } catch (caught) {
      if (operation === expectedOperation && !isAbortError(caught)) {
        thread.value = null
        messages.value = []
        error.value = errorText(caught)
      }
    } finally {
      if (operation === expectedOperation) loading.value = false
    }
  }

  const uploadFiles = async (files: File[]) => {
    if (files.length === 0) return

    const expectedGeneration = uploadGeneration
    uploadingCount.value += files.length
    uploadError.value = ""
    try {
      const uploaded = await uploadChatAttachments(
        files,
        requireAccessToken()
      )
      if (uploadGeneration !== expectedGeneration) return
      attachments.value = [...attachments.value, ...uploaded]
    } catch (caught) {
      if (uploadGeneration === expectedGeneration) {
        uploadError.value = errorText(caught)
      }
    } finally {
      if (uploadGeneration === expectedGeneration) {
        uploadingCount.value = Math.max(
          0,
          uploadingCount.value - files.length
        )
      }
    }
  }

  const removeAttachment = (fileId: string) => {
    attachments.value = attachments.value.filter(
      (attachment) => attachment.file_id !== fileId
    )
  }

  const createOptimisticMessage = (
    content: string,
    selectedAttachments: UploadedAttachmentResponse[]
  ): ThreadMessageResponse => {
    const createdAt = new Date().toISOString()
    return {
      message_id: optimisticMessageId--,
      role: "user",
      content,
      image_content: null,
      message_type: selectedAttachments.length
        ? content ? "multimodal" : "attachment"
        : "text",
      status: "pending",
      request_id: null,
      run: null,
      attachments: selectedAttachments.map((attachment) => ({
        file_id: attachment.file_id,
        file_name: attachment.file_name,
        content_type: attachment.content_type,
        file_size: attachment.file_size,
        available: true,
        access_url: attachment.access_url
      })),
      created_at: createdAt,
      updated_at: createdAt
    }
  }

  const submitDraft = async (onThreadCreated?: ThreadCreatedHandler) => {
    const draftSnapshot = draft.value
    const query = draftSnapshot.trim()
    const attachmentSnapshot = [...attachments.value]
    if (
      (!query && attachmentSnapshot.length === 0) ||
      uploadingCount.value > 0 ||
      submitting.value ||
      isRunActive.value
    ) {
      return
    }

    const expectedOperation = ++operation
    const optimisticMessage = createOptimisticMessage(
      query,
      attachmentSnapshot
    )
    messages.value = [...messages.value, optimisticMessage]
    draft.value = ""
    attachments.value = []
    uploadError.value = ""
    abortStream()
    submitting.value = true
    error.value = ""
    let runCreated = false

    try {
      const accessToken = requireAccessToken()
      let currentThread = thread.value

      if (!currentThread) {
        const agents = await listChatAgents(accessToken)
        const leader = agents.find((agent) => agent.id === "LeaderAgent")
        if (!leader) throw new Error("LeaderAgent 当前不可用")

        const created = await createThread(leader.id, accessToken)
        if (operation !== expectedOperation) return
        currentThread = {
          thread_id: created.thread_id,
          title: created.title,
          summary: null,
          agent_id: created.agent_id,
          metadata: created.metadata,
          created_at: created.created_at,
          updated_at: created.updated_at,
          last_message_at: null
        }
        thread.value = currentThread
        await onThreadCreated?.(created.thread_id)
      }

      if (operation !== expectedOperation) return
      const run = await createAgentRun(
        query,
        currentThread.agent_id,
        currentThread.thread_id,
        attachmentSnapshot.map((attachment) => attachment.file_id),
        accessToken
      )
      if (operation !== expectedOperation) return
      runCreated = true

      runId.value = run.run_id
      runStatus.value = run.status
      streamUrl.value = run.stream_url

      try {
        await applyThreadDetail(
          currentThread.thread_id,
          accessToken,
          expectedOperation
        )
      } catch (caught) {
        if (operation === expectedOperation && !isAbortError(caught)) {
          error.value = errorText(caught)
        }
      }
      if (operation !== expectedOperation) return
      if (run.status === "failed") {
        error.value = "Agent 执行失败"
      }

      await monitorRun(
        currentThread.thread_id,
        accessToken,
        expectedOperation
      )
    } catch (caught) {
      if (operation === expectedOperation && !isAbortError(caught)) {
        error.value = errorText(caught)
        if (
          !runCreated &&
          messages.value.some(
            (message) =>
              message.message_id === optimisticMessage.message_id
          )
        ) {
          messages.value = messages.value.filter(
            (message) =>
              message.message_id !== optimisticMessage.message_id
          )
          draft.value = draftSnapshot
          attachments.value = attachmentSnapshot
        }
      }
    } finally {
      if (operation === expectedOperation) {
        streamController = null
        streamUrl.value = null
        submitting.value = false
      }
    }
  }

  const cancelCurrentRun = async () => {
    if (!runId.value || cancelling.value || !isRunActive.value) return
    const targetRunId = runId.value
    const expectedOperation = operation
    cancelling.value = true
    error.value = ""
    try {
      const response = await cancelAgentRun(
        targetRunId,
        requireAccessToken()
      )
      if (
        operation !== expectedOperation ||
        runId.value !== targetRunId
      ) {
        return
      }
      runStatus.value = response.status
    } catch (caught) {
      if (
        operation === expectedOperation &&
        runId.value === targetRunId
      ) {
        error.value = errorText(caught)
      }
    } finally {
      if (
        operation === expectedOperation &&
        runId.value === targetRunId
      ) {
        cancelling.value = false
      }
    }
  }

  const stop = () => {
    operation += 1
    uploadGeneration += 1
    abortStream()
  }

  return {
    thread,
    messages,
    draft,
    attachments,
    uploadingCount,
    uploadError,
    runId,
    runStatus,
    streamUrl,
    loading,
    submitting,
    cancelling,
    error,
    isRunActive,
    loadThread,
    resetThread,
    uploadFiles,
    removeAttachment,
    submitDraft,
    cancelCurrentRun,
    stop
  }
}
