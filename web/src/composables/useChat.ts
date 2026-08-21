import { ref } from "vue"

import type { UploadedAttachmentResponse } from "@/types/attachment"
import type {
  AgentRunStreamEvent,
  ChatMessage,
  ThreadDetailResponse,
  ThreadMessageResponse,
  ThreadResponse,
  ThreadSummaryResponse
} from "@/types/chat"

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null

const toChatMessage = (message: ThreadMessageResponse): ChatMessage => ({
  type: message.role === "user" ? "human" : "ai",
  payload: {
    type: "text",
    event: message
  }
})

const chatMessageEvent = (message: ChatMessage) =>
  isRecord(message.payload.event) ? message.payload.event : null

const chatMessageId = (message: ChatMessage) =>
  chatMessageEvent(message)?.message_id

export const useChat = () => {
  const thread = ref<ThreadSummaryResponse | null>(null)
  const messages = ref<ChatMessage[]>([])
  const draft = ref("")
  const attachments = ref<UploadedAttachmentResponse[]>([])
  const uploadingCount = ref(0)
  const uploadError = ref("")
  const loading = ref(false)
  const submitting = ref(false)
  const error = ref("")

  let optimisticMessageId = -1

  const clearPendingInput = () => {
    draft.value = ""
    attachments.value = []
    uploadingCount.value = 0
    uploadError.value = ""
  }

  const applyThreadDetail = (detail: ThreadDetailResponse) => {
    thread.value = detail.thread
    messages.value = detail.messages.map(toChatMessage)
  }

  const applyCreatedThread = (
    created: ThreadResponse
  ): ThreadSummaryResponse => {
    const createdThread = {
      thread_id: created.thread_id,
      title: created.title,
      summary: null,
      agent_id: created.agent_id,
      metadata: created.metadata,
      created_at: created.created_at,
      updated_at: created.updated_at,
      last_message_at: null
    }
    thread.value = createdThread
    return createdThread
  }

  const clearRunStreamMessages = (targetRunId: string) => {
    messages.value = messages.value.filter((message) => {
      if (message.type !== "ai") return true
      const event = chatMessageEvent(message)
      if (event?.run_id !== targetRunId) return true
      return !(
        message.payload.type === "tool" ||
        event.status === "streaming"
      )
    })
  }

  const appendAiText = (
    messageId: string,
    contentDelta: string,
    threadId: string | null,
    event: AgentRunStreamEvent,
    monitoredRunId: string
  ) => {
    const messageIndex = messages.value.findIndex(
      (message) =>
        message.type === "ai" &&
        message.payload.type === "text" &&
        chatMessageId(message) === messageId
    )

    if (messageIndex === -1) {
      messages.value = [
        ...messages.value,
        {
          type: "ai",
          payload: {
            type: "text",
            event: {
              message_id: messageId,
              thread_id: threadId,
              run_id: monitoredRunId,
              content: contentDelta,
              status: "streaming",
              attachments: [],
              created_at: event.created_at
            }
          }
        }
      ]
      return
    }

    const message = messages.value[messageIndex]
    if (!message) return
    const currentEvent = chatMessageEvent(message)
    if (!currentEvent) return
    const currentContent = typeof currentEvent.content === "string"
      ? currentEvent.content
      : ""
    const nextMessages = [...messages.value]
    nextMessages[messageIndex] = {
      ...message,
      payload: {
        ...message.payload,
        event: {
          ...currentEvent,
          content: currentContent + contentDelta
        }
      }
    }
    messages.value = nextMessages
  }

  const applyAiTextDelta = (
    event: AgentRunStreamEvent,
    monitoredRunId: string
  ) => {
    if (!Array.isArray(event.items)) return

    for (const item of event.items) {
      if (!isRecord(item) || !Array.isArray(item.stream_event)) continue
      for (const messageEvent of item.stream_event) {
        if (
          !isRecord(messageEvent) ||
          messageEvent.type !== "message_delta" ||
          typeof messageEvent.message_id !== "string" ||
          typeof messageEvent.content_delta !== "string"
        ) {
          continue
        }
        appendAiText(
          messageEvent.message_id,
          messageEvent.content_delta,
          typeof messageEvent.thread_id === "string"
            ? messageEvent.thread_id
            : event.thread_id,
          event,
          monitoredRunId
        )
      }
    }
  }

  const applyRunMessageEvent = (
    event: AgentRunStreamEvent,
    monitoredRunId: string
  ) => {
    if (event.type === "messages") {
      applyAiTextDelta(event, monitoredRunId)
      return
    }
    if (event.type !== "custom" || event.name !== "agent_state") return

    const messageIndex = messages.value.findIndex((message) => {
      const messageEvent = chatMessageEvent(message)
      return (
        message.type === "ai" &&
        message.payload.type === "tool" &&
        messageEvent?.id === event.id
      )
    })
    const toolMessage: ChatMessage = {
      type: "ai",
      payload: {
        type: "tool",
        event
      }
    }
    if (messageIndex === -1) {
      messages.value = [...messages.value, toolMessage]
      return
    }
    const nextMessages = [...messages.value]
    nextMessages[messageIndex] = toolMessage
    messages.value = nextMessages
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

  const beginSubmission = () => {
    const draftSnapshot = draft.value
    const query = draftSnapshot.trim()
    const attachmentSnapshot = [...attachments.value]
    if (
      (!query && attachmentSnapshot.length === 0) ||
      uploadingCount.value > 0 ||
      submitting.value
    ) {
      return null
    }

    const optimisticMessage = createOptimisticMessage(
      query,
      attachmentSnapshot
    )
    messages.value = [...messages.value, toChatMessage(optimisticMessage)]
    draft.value = ""
    attachments.value = []
    uploadError.value = ""
    submitting.value = true
    error.value = ""
    return {
      query,
      draft: draftSnapshot,
      attachments: attachmentSnapshot,
      optimisticMessageId: optimisticMessage.message_id
    }
  }

  const rollbackSubmission = (
    submission: NonNullable<ReturnType<typeof beginSubmission>>
  ) => {
    messages.value = messages.value.filter(
      (message) => chatMessageId(message) !== submission.optimisticMessageId
    )
    draft.value = submission.draft
    attachments.value = submission.attachments
  }

  const appendUploadedAttachments = (
    uploaded: UploadedAttachmentResponse[]
  ) => {
    attachments.value = [...attachments.value, ...uploaded]
  }

  const removeAttachment = (fileId: string) => {
    attachments.value = attachments.value.filter(
      (attachment) => attachment.file_id !== fileId
    )
  }

  const resetThread = () => {
    thread.value = null
    messages.value = []
    clearPendingInput()
    error.value = ""
    loading.value = false
    submitting.value = false
  }

  return {
    thread,
    messages,
    draft,
    attachments,
    uploadingCount,
    uploadError,
    loading,
    submitting,
    error,
    clearPendingInput,
    applyThreadDetail,
    applyCreatedThread,
    clearRunStreamMessages,
    applyRunMessageEvent,
    beginSubmission,
    rollbackSubmission,
    appendUploadedAttachments,
    removeAttachment,
    resetThread
  }
}
