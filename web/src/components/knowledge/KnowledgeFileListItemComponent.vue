<script setup lang="ts">
import { FileText } from "@lucide/vue"

import type { KnowledgeFileItem } from "@/types/knowledge"

import KnowledgeFileActionsMenuComponent from "./KnowledgeFileActionsMenuComponent.vue"

const props = defineProps<{
  file: KnowledgeFileItem
  selected: boolean
}>()

const emit = defineEmits<{
  select: [fileId: string]
  remove: [fileId: string]
}>()
</script>

<template>
  <li
    class="knowledge-file-row"
    :class="{ 'is-selected': props.selected }"
  >
    <button
      class="knowledge-file-select"
      type="button"
      :aria-current="props.selected ? 'true' : undefined"
      @click="emit('select', props.file.id)"
    >
      <span class="knowledge-file-type" aria-hidden="true">
        <FileText :size="17" :stroke-width="1.7" />
      </span>

      <span class="knowledge-file-copy">
        <strong class="knowledge-file-name" :title="props.file.name">
          {{ props.file.name }}
        </strong>
      </span>
    </button>

    <KnowledgeFileActionsMenuComponent
      :file="props.file"
      @remove="emit('remove', $event)"
    />
  </li>
</template>

<style scoped>
@reference "../../styles/index.css";

.knowledge-file-row {
  @apply grid min-w-0 items-center;

  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.15rem;
  min-height: 3.5rem;
  padding: 0.3rem 0.35rem 0.3rem 0.5rem;
  border: 1px solid transparent;
  border-radius: var(--radius-knowledge-container);
  transition:
    border-color 120ms ease,
    background-color 120ms ease;
}

.knowledge-file-row:hover {
  background: var(--color-surface-muted);
}

.knowledge-file-row.is-selected {
  border-color: var(--color-border-control);
  background: var(--color-surface-emphasis);
}

.knowledge-file-select {
  @apply grid min-w-0 items-center border-0 bg-transparent p-0 text-left;

  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.55rem;
}

.knowledge-file-type {
  @apply grid shrink-0 place-items-center;

  width: 2rem;
  height: 2rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-knowledge-container);
  color: var(--color-text-muted);
  background: var(--color-surface);
}

.knowledge-file-row.is-selected .knowledge-file-type {
  color: var(--color-on-action);
  background: var(--color-action-primary);
}

.knowledge-file-copy {
  @apply min-w-0;
}

.knowledge-file-name {
  @apply overflow-hidden text-ellipsis whitespace-nowrap font-medium;
}
</style>
