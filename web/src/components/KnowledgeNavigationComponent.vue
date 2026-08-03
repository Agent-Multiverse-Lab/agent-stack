<script setup lang="ts">
import { Button as AButton } from "ant-design-vue"
import {
  ArrowLeft,
  BookOpenCheck,
  Files,
  MessagesSquare,
  WandSparkles
} from "@lucide/vue"

const props = defineProps<{
  compactMode: boolean
  filesOpen: boolean
  actionsOpen: boolean
}>()

const emit = defineEmits<{
  back: []
  files: []
  chat: []
  actions: []
}>()
</script>

<template>
  <aside class="knowledge-navigation" aria-label="Knowledge workspace navigation">
    <div class="knowledge-navigation-inner">
      <div class="knowledge-navigation-mark" aria-hidden="true">
        <BookOpenCheck :size="20" :stroke-width="1.8" />
        <span class="knowledge-navigation-label">Knowledge</span>
      </div>

      <nav class="knowledge-navigation-actions" aria-label="Knowledge areas">
        <AButton
          class="knowledge-navigation-button"
          type="text"
          aria-label="Back to chat"
          title="Back to chat"
          @click="emit('back')"
        >
          <ArrowLeft :size="19" :stroke-width="1.8" aria-hidden="true" />
          <span class="knowledge-navigation-label">Back</span>
        </AButton>

        <AButton
          id="knowledge-files-trigger"
          class="knowledge-navigation-button"
          type="text"
          aria-label="Open files"
          title="Files"
          :aria-expanded="props.compactMode ? props.filesOpen : undefined"
          aria-controls="knowledge-files-region"
          @click="emit('files')"
        >
          <Files :size="19" :stroke-width="1.8" aria-hidden="true" />
          <span class="knowledge-navigation-label">Files</span>
        </AButton>

        <AButton
          class="knowledge-navigation-button is-active"
          type="text"
          aria-label="Focus knowledge chat"
          title="Chat"
          aria-current="page"
          @click="emit('chat')"
        >
          <MessagesSquare :size="19" :stroke-width="1.9" aria-hidden="true" />
          <span class="knowledge-navigation-label">Chat</span>
        </AButton>

        <AButton
          id="knowledge-actions-trigger"
          class="knowledge-navigation-button"
          type="text"
          aria-label="Open tools"
          title="Tools"
          :aria-expanded="props.compactMode ? props.actionsOpen : undefined"
          aria-controls="knowledge-actions-region"
          @click="emit('actions')"
        >
          <WandSparkles :size="19" :stroke-width="1.8" aria-hidden="true" />
          <span class="knowledge-navigation-label">Tools</span>
        </AButton>
      </nav>
    </div>
  </aside>
</template>

<style scoped>
@reference "../styles/index.css";

.knowledge-navigation {
  @apply relative h-full min-h-0 min-w-0;

  z-index: 10;
}

.knowledge-navigation-inner {
  @apply absolute inset-y-0 left-0 flex min-h-0 flex-col overflow-hidden;

  width: 100%;
  padding: 0.55rem;
  border-right: 1px solid var(--color-border-subtle);
  background: var(--color-surface-muted);
  transition: width 180ms ease-out;
}

.knowledge-navigation:hover .knowledge-navigation-inner,
.knowledge-navigation:focus-within .knowledge-navigation-inner {
  width: 11rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
}

.knowledge-navigation-mark,
.knowledge-navigation-button {
  @apply flex min-w-0 items-center overflow-hidden whitespace-nowrap;

  width: 100%;
  min-height: 2.75rem;
  gap: 0.8rem;
  padding-inline: 0.72rem;
  border-radius: var(--radius-md);
}

.knowledge-navigation-mark {
  @apply shrink-0;

  color: var(--color-on-action);
  background: var(--color-action-primary);
}

.knowledge-navigation-actions {
  @apply flex flex-1 flex-col justify-center;

  gap: 0.35rem;
}

.knowledge-navigation-button {
  @apply justify-start;

  color: var(--color-text-muted);
}

.knowledge-navigation-button :deep(svg),
.knowledge-navigation-mark :deep(svg) {
  @apply shrink-0;
}

.knowledge-navigation-button:hover,
.knowledge-navigation-button:focus-visible {
  color: var(--color-text);
  background: var(--color-surface-hover);
}

.knowledge-navigation-button.is-active {
  color: var(--color-on-action);
  background: var(--color-action-primary);
}

.knowledge-navigation-button.is-active:hover {
  color: var(--color-on-action);
  background: var(--color-action-primary-hover);
}

.knowledge-navigation-label {
  @apply overflow-hidden text-ellipsis whitespace-nowrap font-medium;

  max-width: 0;
  opacity: 0;
  transition:
    max-width 180ms ease-out,
    opacity 100ms ease-out;
}

.knowledge-navigation:hover .knowledge-navigation-label,
.knowledge-navigation:focus-within .knowledge-navigation-label {
  max-width: 7rem;
  opacity: 1;
}

@media (max-width: 720px) {
  .knowledge-navigation {
    min-height: 3.75rem;
  }

  .knowledge-navigation-inner,
  .knowledge-navigation:hover .knowledge-navigation-inner,
  .knowledge-navigation:focus-within .knowledge-navigation-inner {
    @apply static flex-row items-center justify-between;

    width: 100%;
    height: 100%;
    padding: 0.45rem 0.65rem;
    border: 0;
    border-bottom: 1px solid var(--color-border-subtle);
    border-radius: 0;
    background: var(--color-surface);
  }

  .knowledge-navigation-mark,
  .knowledge-navigation-button {
    width: 2.75rem;
    min-width: 2.75rem;
    padding: 0;
    justify-content: center;
  }

  .knowledge-navigation-actions {
    @apply flex-none flex-row;
  }

  .knowledge-navigation-label,
  .knowledge-navigation:hover .knowledge-navigation-label,
  .knowledge-navigation:focus-within .knowledge-navigation-label {
    @apply hidden;
  }
}
</style>
