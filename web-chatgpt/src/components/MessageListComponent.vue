<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue"
import { CircleAlert, FileText } from "@lucide/vue"

import type { LocalMessage } from "@/types/conversation"

const props = defineProps<{
  messages: LocalMessage[]
  showLocalNotice: boolean
}>()

const messageListElement = ref<HTMLDivElement | null>(null)

const timeFormatter = new Intl.DateTimeFormat("en-US", {
  hour: "2-digit",
  minute: "2-digit",
})

function formatCreatedAt(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? "" : timeFormatter.format(date)
}

const displayedMessages = computed(() =>
  props.messages.map((message) => ({
    message,
    formattedTime: formatCreatedAt(message.createdAt),
  })),
)

watch(
  () => [props.messages.length, props.showLocalNotice],
  async () => {
    await nextTick()
    const element = messageListElement.value
    if (element) {
      element.scrollTop = element.scrollHeight
    }
  },
)
</script>

<template>
  <div
    ref="messageListElement"
    class="message-list"
    aria-label="本地对话记录"
  >
    <div class="message-list-content">
      <article
        v-for="{ message, formattedTime } in displayedMessages"
        :key="message.id"
        class="message-entry"
        aria-label="User message"
      >
        <div class="message-entry-body">
          <p
            v-if="message.content"
            class="message-entry-text"
          >
            {{ message.content }}
          </p>

          <ul
            v-if="message.attachments.length"
            class="message-entry-attachments"
            aria-label="Message attachments"
          >
            <li
              v-for="attachment in message.attachments"
              :key="attachment.id"
              class="message-entry-attachment"
              :title="attachment.name"
            >
              <FileText
                class="message-entry-attachment-icon"
                :size="14"
                :stroke-width="1.8"
                aria-hidden="true"
              />
              <span class="message-entry-attachment-name">
                {{ attachment.name }}
              </span>
            </li>
          </ul>
        </div>

        <time
          v-if="formattedTime"
          class="message-entry-time"
          :datetime="message.createdAt"
        >
          {{ formattedTime }}
        </time>
      </article>

      <aside
        v-if="props.showLocalNotice"
        class="local-conversation-notice"
        role="status"
        aria-live="polite"
      >
        <CircleAlert
          class="local-conversation-notice-icon"
          :size="16"
          :stroke-width="1.8"
          aria-hidden="true"
        />
        <p class="local-conversation-notice-text">
          尚未连接模型 · 仅保存在当前浏览器
        </p>
      </aside>
    </div>
  </div>
</template>

<style scoped>
@reference "../styles/index.css";

.message-list {
  @apply min-h-0 w-full overflow-y-auto overscroll-contain;

  scrollbar-color: var(--color-surface-emphasis) transparent;
}

.message-list-content {
  @apply mx-auto flex min-h-full flex-col justify-end gap-7 pb-5;

  width: min(100%, var(--content-width));
  padding-top: clamp(1.2rem, 3.5vh, 2.4rem);
  padding-inline: clamp(1rem, 3vw, 1.5rem);
}

.message-entry {
  @apply flex w-full flex-col items-end;

  gap: 0.3rem;
}

.message-entry-body {
  @apply grid w-fit;

  max-width: min(78%, 640px);
  gap: 0.55rem;
  padding-block: 0.15rem;
  color: var(--color-text);
}

.message-entry-text {
  @apply m-0 whitespace-pre-wrap;

  overflow-wrap: anywhere;
  font-size: 0.95rem;
  line-height: 1.7;
}

.message-entry-attachments {
  @apply m-0 flex list-none flex-wrap p-0;

  column-gap: 0.85rem;
  row-gap: 0.55rem;
}

.message-entry-attachment {
  @apply flex min-w-0 max-w-60 items-center text-xs;

  gap: 0.35rem;
  color: var(--color-text-muted);
}

.message-entry-attachment-icon {
  @apply shrink-0;
}

.message-entry-attachment-name {
  @apply overflow-hidden text-ellipsis whitespace-nowrap;
}

.message-entry-time {
  @apply pointer-events-none opacity-0;

  padding-right: 0.05rem;
  color: var(--color-text-subtle);
  font-size: 0.68rem;
  transition: opacity 120ms ease;
}

.message-entry:hover .message-entry-time,
.message-entry:focus-within .message-entry-time {
  @apply pointer-events-auto opacity-100;
}

.local-conversation-notice {
  @apply inline-flex max-w-full self-start items-center;

  gap: 0.45rem;
  padding-block: 0.15rem;
  color: var(--color-text-subtle);
}

.local-conversation-notice-icon {
  @apply shrink-0;
}

.local-conversation-notice-text {
  @apply m-0;

  color: var(--color-text-muted);
  font-size: 0.78rem;
  line-height: 1.45;
}

@media (max-width: 640px) {
  .message-entry-body {
    max-width: 92%;
  }
}

@media (hover: none) {
  .message-entry-time {
    @apply pointer-events-auto opacity-100;
  }
}
</style>
