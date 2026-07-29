<script setup lang="ts">
import { computed } from "vue"

import type {
  LocalAttachment,
  LocalMessage,
} from "@/types/conversation"

import MessageInputComponent from "./MessageInputComponent.vue"
import MessageListComponent from "./MessageListComponent.vue"

const props = defineProps<{
  messages: LocalMessage[]
  attachments: LocalAttachment[]
  draft: string
  showLocalNotice: boolean
}>()

const emit = defineEmits<{
  "update:draft": [value: string]
  submit: []
  "files-selected": [files: File[]]
  "remove-attachment": [id: string]
}>()

const isEmpty = computed(
  () => props.messages.length === 0 && !props.showLocalNotice,
)
</script>

<template>
  <main
    class="conversation"
    aria-label="Conversation"
  >
    <div
      v-if="isEmpty"
      class="conversation-empty"
    >
      <div class="conversation-empty-content">
        <section
          class="conversation-greeting"
          aria-labelledby="conversation-greeting"
        >
          <h1
            id="conversation-greeting"
            class="conversation-greeting-title"
          >
            What's on your mind today?
          </h1>
        </section>

        <MessageInputComponent
          class="conversation-empty-input"
          :draft="props.draft"
          :attachments="props.attachments"
          @update:draft="emit('update:draft', $event)"
          @submit="emit('submit')"
          @files-selected="emit('files-selected', $event)"
          @remove-attachment="emit('remove-attachment', $event)"
        />

        <p class="conversation-disclaimer">
          AI can make mistakes. Verify important info.
        </p>
      </div>
    </div>

    <template v-else>
      <div class="conversation-messages">
        <MessageListComponent
          class="conversation-message-list"
          :messages="props.messages"
          :show-local-notice="props.showLocalNotice"
        />
      </div>

      <div class="conversation-input-area">
        <MessageInputComponent
          class="conversation-input"
          :draft="props.draft"
          :attachments="props.attachments"
          @update:draft="emit('update:draft', $event)"
          @submit="emit('submit')"
          @files-selected="emit('files-selected', $event)"
          @remove-attachment="emit('remove-attachment', $event)"
        />

        <p class="conversation-disclaimer">
          AI can make mistakes. Verify important info.
        </p>
      </div>
    </template>
  </main>
</template>

<style scoped>
@reference "../styles/index.css";

.conversation {
  @apply flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden;

  color: var(--color-text);
  background: var(--color-canvas);
}

.conversation-empty {
  @apply flex min-h-0 flex-1 items-center justify-center pt-6 pb-16;

  padding-inline: clamp(1rem, 4vw, 2rem);
}

.conversation-empty-content {
  @apply flex flex-col items-center gap-5;

  width: min(100%, var(--composer-width));
}

.conversation-greeting {
  @apply flex w-full items-center justify-center pb-3 text-center;
}

.conversation-greeting-title {
  @apply m-0;

  color: var(--color-text);
  font-size: clamp(1.75rem, 4vw, 2.15rem);
  font-weight: 550;
  letter-spacing: -0.03em;
  line-height: 1.25;
}

.conversation-empty-input {
  @apply w-full;
}

.conversation-messages {
  @apply flex min-h-0 min-w-0 flex-1 items-center justify-center overflow-hidden;
}

.conversation-message-list {
  @apply min-w-0;
}

.conversation-input-area {
  @apply grid w-full flex-none justify-items-center;

  gap: 0.55rem;
  padding: 0.35rem clamp(1rem, 4vw, 2rem) 0.7rem;
}

.conversation-input {
  width: min(100%, var(--composer-width));
}

.conversation-disclaimer {
  @apply m-0 text-center;

  color: var(--color-text-subtle);
  font-size: 0.68rem;
  line-height: 1.4;
}

@media (max-width: 560px) {
  .conversation-empty {
    padding: 1rem 0.9rem 2.5rem;
  }

  .conversation-input-area {
    gap: 0.4rem;
    padding: 0.25rem 0.9rem max(0.45rem, env(safe-area-inset-bottom));
  }
}
</style>
