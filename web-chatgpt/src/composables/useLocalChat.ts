import { computed, ref, watch } from "vue"

import type {
  LocalAttachment,
  LocalConversation,
  LocalMessage
} from "@/types/conversation"

const STORAGE_KEY = "opengpt.design.conversations.v1"
const MAX_ATTACHMENTS = 8

const conversations = ref<LocalConversation[]>([])
const activeConversationId = ref<string | null>(null)
const draft = ref("")
const attachments = ref<LocalAttachment[]>([])

let initialized = false

const makeId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`

const normalizeTitle = (content: string) => {
  const compact = content.replace(/\s+/g, " ").trim()
  if (!compact) return "含附件的新对话"
  return compact.length > 28 ? `${compact.slice(0, 28)}…` : compact
}

const readStoredConversations = (): LocalConversation[] => {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (!stored) return []

    const parsed: unknown = JSON.parse(stored)
    if (!Array.isArray(parsed)) return []

    return parsed.filter(
      (item): item is LocalConversation =>
        typeof item === "object" &&
        item !== null &&
        "id" in item &&
        "title" in item &&
        "messages" in item &&
        Array.isArray(item.messages)
    )
  } catch {
    return []
  }
}

const initialize = () => {
  if (initialized) return

  conversations.value = readStoredConversations()
  watch(
    conversations,
    (value) => {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
    },
    { deep: true }
  )
  initialized = true
}

const activeConversation = computed(
  () =>
    conversations.value.find(
      (conversation) => conversation.id === activeConversationId.value
    ) ?? null
)

const messages = computed(() => activeConversation.value?.messages ?? [])

const clearComposer = () => {
  draft.value = ""
  attachments.value = []
}

const selectConversation = (conversationId: string | null) => {
  activeConversationId.value = conversations.value.some(
    (conversation) => conversation.id === conversationId
  )
    ? conversationId
    : null
}

const startNewConversation = () => {
  activeConversationId.value = null
  clearComposer()
}

const addFiles = (files: File[]) => {
  const existing = new Set(
    attachments.value.map(
      (attachment) => `${attachment.name}:${attachment.size}`
    )
  )
  const additions: LocalAttachment[] = []

  for (const file of files) {
    if (attachments.value.length + additions.length >= MAX_ATTACHMENTS) break

    const key = `${file.name}:${file.size}`
    if (existing.has(key)) continue

    existing.add(key)
    additions.push({
      id: makeId(),
      name: file.name,
      size: file.size
    })
  }

  attachments.value = [...attachments.value, ...additions]
}

const removeAttachment = (attachmentId: string) => {
  attachments.value = attachments.value.filter(
    (attachment) => attachment.id !== attachmentId
  )
}

const addMessage = (
  content: string,
  pendingAttachments: LocalAttachment[]
): string => {
  const now = new Date().toISOString()
  const message: LocalMessage = {
    id: makeId(),
    role: "user",
    content,
    createdAt: now,
    attachments: pendingAttachments
  }

  const current = activeConversation.value
  if (current) {
    current.messages.push(message)
    current.updatedAt = now
    conversations.value = [
      current,
      ...conversations.value.filter(
        (conversation) => conversation.id !== current.id
      )
    ]
    return current.id
  }

  const conversation: LocalConversation = {
    id: makeId(),
    title: normalizeTitle(content),
    updatedAt: now,
    messages: [message]
  }
  conversations.value.unshift(conversation)
  activeConversationId.value = conversation.id
  return conversation.id
}

export const useLocalChat = () => {
  initialize()

  return {
    conversations,
    activeConversation,
    activeConversationId,
    messages,
    draft,
    attachments,
    addFiles,
    addMessage,
    clearComposer,
    removeAttachment,
    selectConversation,
    startNewConversation
  }
}
