<script setup lang="ts">
import { computed, watch } from "vue"
import { useRouter } from "vue-router"

import ConversationComponent from "@/components/ConversationComponent.vue"
import { useLocalChat } from "@/composables/useLocalChat"

const props = defineProps<{
  conversationId?: string
}>()

const router = useRouter()
const {
  messages,
  draft,
  attachments,
  addFiles,
  addMessage,
  clearComposer,
  removeAttachment,
  selectConversation
} = useLocalChat()

const showLocalNotice = computed(() => messages.value.length > 0)

watch(
  () => props.conversationId,
  (conversationId) => {
    selectConversation(conversationId ?? null)
    clearComposer()
  },
  { immediate: true }
)

const submitLocalMessage = async () => {
  const content = draft.value.trim()
  if (!content && attachments.value.length === 0) return

  const conversationId = addMessage(content, [...attachments.value])
  clearComposer()

  if (props.conversationId !== conversationId) {
    await router.push({
      name: "conversation",
      params: { conversationId }
    })
  }
}
</script>

<template>
  <ConversationComponent
    class="chat-view"
    :messages="messages"
    :attachments="attachments"
    :draft="draft"
    :show-local-notice="showLocalNotice"
    @update:draft="draft = $event"
    @submit="submitLocalMessage"
    @files-selected="addFiles"
    @remove-attachment="removeAttachment"
  />
</template>

<style scoped>
@reference "../styles/index.css";

.chat-view {
  @apply h-full min-h-0;
}
</style>
