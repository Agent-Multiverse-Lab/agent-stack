<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue"
import { Search, X } from "@lucide/vue"

import type { LocalConversation } from "@/types/conversation"

const props = defineProps<{
  open: boolean
  conversations: LocalConversation[]
}>()

const emit = defineEmits<{
  close: []
  select: [conversationId: string]
}>()

const query = ref("")
const inputElement = ref<HTMLInputElement | null>(null)

const results = computed(() => {
  const normalizedQuery = query.value.trim().toLocaleLowerCase()
  if (!normalizedQuery) {
    return props.conversations
  }

  return props.conversations.filter((conversation) =>
    conversation.title.toLocaleLowerCase().includes(normalizedQuery),
  )
})

function closeOnEscape(event: KeyboardEvent) {
  if (event.key === "Escape") {
    emit("close")
  }
}

function selectConversation(conversationId: string) {
  emit("select", conversationId)
  emit("close")
}

watch(
  () => props.open,
  async (open) => {
    document.body.toggleAttribute("data-modal-open", open)

    if (!open) {
      document.removeEventListener("keydown", closeOnEscape)
      return
    }

    query.value = ""
    document.addEventListener("keydown", closeOnEscape)
    await nextTick()
    inputElement.value?.focus()
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  document.body.removeAttribute("data-modal-open")
  document.removeEventListener("keydown", closeOnEscape)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="conversation-search">
      <div
        v-if="props.open"
        class="conversation-search-backdrop"
        @mousedown.self="emit('close')"
      >
        <section
          class="conversation-search-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="conversation-search-title"
        >
          <header class="conversation-search-heading">
            <h2
              id="conversation-search-title"
              class="conversation-search-title"
            >
              Search chats
            </h2>

            <button
              class="conversation-search-close"
              type="button"
              aria-label="Close"
              title="Close"
              @click="emit('close')"
            >
              <X
                class="conversation-search-close-icon"
                :size="19"
                :stroke-width="1.8"
                aria-hidden="true"
              />
            </button>
          </header>

          <div class="conversation-search-content">
            <label class="conversation-search-field">
              <Search
                class="conversation-search-icon"
                :size="17"
                :stroke-width="1.8"
                aria-hidden="true"
              />
              <span class="conversation-search-label">Search query</span>
              <input
                ref="inputElement"
                v-model="query"
                class="conversation-search-input"
                type="search"
                autocomplete="off"
                placeholder="Search title"
              >
            </label>

            <div
              class="conversation-search-results"
              aria-live="polite"
            >
              <button
                v-for="conversation in results"
                :key="conversation.id"
                class="conversation-search-result"
                type="button"
                @click="selectConversation(conversation.id)"
              >
                <span class="conversation-search-result-title">
                  {{ conversation.title }}
                </span>
              </button>

              <p
                v-if="results.length === 0"
                class="conversation-search-empty"
              >
                {{
                  props.conversations.length === 0
                    ? "No conversations"
                    : "No matches found"
                }}
              </p>
            </div>
          </div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
@reference "../styles/index.css";

.conversation-search-backdrop {
  @apply fixed inset-0 grid place-items-center p-5;

  z-index: 100;
  background: var(--color-overlay);
}

.conversation-search-dialog {
  @apply flex w-full flex-col overflow-hidden;

  width: min(100%, 520px);
  max-height: min(720px, calc(100dvh - 40px));
  border-radius: var(--radius-lg);
  color: var(--color-text);
  background: var(--color-surface);
}

.conversation-search-heading {
  @apply flex items-start justify-between gap-4 pt-5 pb-3;

  padding-inline: 1.35rem;
}

.conversation-search-title {
  @apply m-0 text-base font-semibold;

  letter-spacing: -0.02em;
}

.conversation-search-close {
  @apply grid size-9 shrink-0 place-items-center bg-transparent;

  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
}

.conversation-search-close:hover {
  color: var(--color-text);
  background: var(--color-surface-muted);
}

.conversation-search-close-icon {
  @apply shrink-0;
}

.conversation-search-content {
  @apply min-h-0 overflow-auto;

  padding: 0 1.35rem 1.35rem;
}

.conversation-search-field {
  @apply flex min-h-10 items-center gap-2 border-b;

  padding-bottom: 0.55rem;
  border-color: var(--color-border);
  color: var(--color-text-muted);
}

.conversation-search-field:focus-within {
  border-color: var(--color-border-focus);
  color: var(--color-text);
}

.conversation-search-icon {
  @apply shrink-0;
}

.conversation-search-label {
  @apply absolute h-px w-px overflow-hidden whitespace-nowrap;

  clip: rect(0 0 0 0);
  clip-path: inset(50%);
}

.conversation-search-input {
  @apply min-w-0 flex-1 border-0 bg-transparent outline-none;

  font-size: 0.92rem;
}

.conversation-search-input::placeholder {
  color: var(--color-text-subtle);
}

.conversation-search-input:focus-visible {
  outline: none;
}

.conversation-search-results {
  @apply grid gap-0 overflow-auto pt-2;

  max-height: 360px;
}

.conversation-search-result {
  @apply flex w-full items-center bg-transparent text-left;

  min-height: 2.4rem;
  padding: 0.45rem 0.15rem;
  border-radius: var(--radius-sm);
  font-size: 0.9rem;
}

.conversation-search-result:hover {
  background: var(--color-surface-muted);
}

.conversation-search-result-title {
  @apply overflow-hidden text-ellipsis whitespace-nowrap;
}

.conversation-search-empty {
  @apply m-0 px-1 py-7 text-left;

  color: var(--color-text-subtle);
  font-size: 0.86rem;
}

.conversation-search-enter-active {
  transition: opacity 150ms ease-out;
}

.conversation-search-leave-active {
  transition: opacity 150ms ease-in;
}

.conversation-search-enter-from,
.conversation-search-leave-to {
  opacity: 0;
}

@media (max-width: 560px) {
  .conversation-search-backdrop {
    @apply items-end p-0;
  }

  .conversation-search-dialog {
    max-height: 88dvh;
    border-bottom-right-radius: 0;
    border-bottom-left-radius: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .conversation-search-enter-active,
  .conversation-search-leave-active {
    transition: none;
  }
}
</style>
