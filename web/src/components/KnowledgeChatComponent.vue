<script setup lang="ts">
import { computed } from "vue"
import { Empty as AEmpty } from "ant-design-vue"
import { MessagesSquare } from "@lucide/vue"

import type { KnowledgeFileItem } from "@/types/knowledge"

import KnowledgeComposerComponent from "./KnowledgeComposerComponent.vue"

const props = defineProps<{
  files: KnowledgeFileItem[]
}>()

const chatEnabled = computed(() =>
  props.files.some((file) => file.status === "indexed")
)
</script>

<template>
  <section
    id="knowledge-chat-region"
    class="knowledge-chat"
    tabindex="-1"
    aria-labelledby="knowledge-chat-title"
  >
    <header class="knowledge-chat-header">
      <h1 id="knowledge-chat-title">Knowledge Chat</h1>
    </header>

    <div class="knowledge-chat-body">
      <AEmpty class="knowledge-chat-empty">
        <template #image>
          <span class="knowledge-chat-empty-mark" aria-hidden="true">
            <MessagesSquare :size="28" :stroke-width="1.45" />
          </span>
        </template>
        <template #description>
          <strong class="knowledge-chat-empty-copy">No indexed files</strong>
        </template>
      </AEmpty>
    </div>

    <KnowledgeComposerComponent
      :enabled="chatEnabled"
    />
  </section>
</template>

<style scoped>
@reference "../styles/index.css";

.knowledge-chat {
  @apply grid h-full min-h-0 min-w-0 overflow-hidden border;

  grid-template-rows: auto minmax(0, 1fr) auto;
  border-color: var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
}

.knowledge-chat:focus-visible {
  outline-offset: -3px;
}

.knowledge-chat-header {
  @apply flex min-w-0 items-center;

  min-height: 4.5rem;
  padding: 0.85rem 1.2rem;
  border-bottom: 1px solid var(--color-border-subtle);
}

.knowledge-chat-header h1 {
  @apply m-0 overflow-hidden text-ellipsis whitespace-nowrap font-semibold;

  font-size: 1rem;
  letter-spacing: -0.03em;
}

.knowledge-chat-body {
  @apply min-h-0 overflow-y-auto overscroll-contain;

  background: var(--color-surface-muted);
}

.knowledge-chat-empty {
  @apply grid h-full place-content-center;

  max-width: 25rem;
  min-height: 18rem;
  margin: auto;
  padding: 2rem;
}

.knowledge-chat-empty :deep(.ant-empty-image) {
  @apply grid place-items-center;

  height: auto;
  margin-bottom: 0.9rem;
}

.knowledge-chat-empty-mark {
  @apply grid place-items-center;

  width: 3.4rem;
  height: 3.4rem;
  border: 1px solid var(--color-border-control);
  border-radius: var(--radius-lg);
  color: var(--color-text-muted);
  background: var(--color-surface);
}

.knowledge-chat-empty-copy {
  color: var(--color-text);
  font-size: 0.96rem;
  letter-spacing: -0.02em;
}

@media (max-width: 720px) {
  .knowledge-chat-header {
    min-height: 4.15rem;
    padding-inline: 1rem;
  }

  .knowledge-chat {
    border-right: 0;
    border-bottom: 0;
    border-left: 0;
    border-radius: 0;
  }
}
</style>
