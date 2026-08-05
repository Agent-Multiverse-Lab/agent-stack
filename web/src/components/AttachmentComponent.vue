<script setup lang="ts">
import { computed } from "vue"
import { File as FileIcon, X } from "@lucide/vue"

import type { LocalAttachment } from "@/types/conversation"

const props = defineProps<{
  attachment: LocalAttachment
}>()

const emit = defineEmits<{
  remove: [id: string]
}>()

function formatFileSize(size: number): string {
  if (size < 1024) {
    return `${size} B`
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

function getFileType(name: string): string {
  const extension = name.match(/\.([^.]+)$/)?.[1]
  return extension ? extension.toUpperCase() : "FILE"
}

const attachmentMeta = computed(
  () =>
    `${getFileType(props.attachment.name)} · ${formatFileSize(props.attachment.size)}`,
)
</script>

<template>
  <li class="attachment">
    <span
      class="attachment-icon"
      aria-hidden="true"
    >
      <FileIcon
        :size="15"
        :stroke-width="1.8"
      />
    </span>

    <span class="attachment-details">
      <strong
        class="attachment-name"
        :title="props.attachment.name"
      >
        {{ props.attachment.name }}
      </strong>
      <span class="attachment-meta">
        {{ attachmentMeta }}
      </span>
    </span>

    <button
      class="attachment-remove"
      type="button"
      :aria-label="`Remove attachment ${props.attachment.name}`"
      :title="`Remove ${props.attachment.name}`"
      @click="emit('remove', props.attachment.id)"
    >
      <X
        :size="14"
        :stroke-width="1.9"
        aria-hidden="true"
      />
    </button>
  </li>
</template>

<style scoped>
@reference "../styles/index.css";

.attachment {
  @apply grid shrink-0 items-center border;

  width: 208px;
  min-width: 208px;
  height: 44px;
  grid-template-columns: 28px minmax(0, 1fr) 28px;
  gap: 0.4rem;
  padding: 0.25rem 0.35rem;
  border-color: var(--color-border-subtle);
  border-radius: var(--radius-pill);
  color: var(--color-text);
  background: var(--color-surface);
}

.attachment-icon,
.attachment-remove {
  @apply grid size-7 shrink-0 place-items-center;

  border-radius: var(--radius-pill);
}

.attachment-icon {
  color: var(--color-text-muted);
  background: var(--color-surface-emphasis);
}

.attachment-details {
  @apply grid min-w-0;

  gap: 0.05rem;
}

.attachment-name {
  @apply overflow-hidden text-ellipsis whitespace-nowrap font-medium;

  font-size: 0.75rem;
  line-height: 1.15;
}

.attachment-meta {
  @apply overflow-hidden text-ellipsis whitespace-nowrap;

  color: var(--color-text-subtle);
  font-family: var(--font-utility);
  font-size: 0.61rem;
  line-height: 1.15;
  letter-spacing: 0.01em;
}

.attachment-remove {
  @apply bg-transparent;

  color: var(--color-text-subtle);
  transition:
    color 120ms ease,
    background-color 120ms ease;
}

.attachment-remove:hover {
  color: var(--color-on-action);
  background: var(--color-action-primary);
}

@media (prefers-reduced-motion: reduce) {
  .attachment-remove {
    transition: none;
  }
}
</style>
