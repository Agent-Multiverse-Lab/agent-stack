<script setup lang="ts">
import { Empty as AEmpty, List as AList } from "ant-design-vue"
import { Files } from "@lucide/vue"

import type { KnowledgeFileItem } from "@/types/knowledge"

import KnowledgeFileListItemComponent from "./KnowledgeFileListItemComponent.vue"

const props = defineProps<{
  files: KnowledgeFileItem[]
  selectedFileId: string | null
}>()

const emit = defineEmits<{
  select: [fileId: string]
  remove: [fileId: string]
}>()
</script>

<template>
  <AList
    v-if="props.files.length"
    class="knowledge-file-list"
    :data-source="props.files"
    :split="false"
  >
    <template #renderItem="{ item }">
      <KnowledgeFileListItemComponent
        :file="item"
        :selected="item.id === props.selectedFileId"
        @select="emit('select', $event)"
        @remove="emit('remove', $event)"
      />
    </template>
  </AList>

  <AEmpty v-else class="knowledge-file-list-empty">
    <template #image>
      <span class="knowledge-file-list-empty-mark" aria-hidden="true">
        <Files :size="25" :stroke-width="1.5" />
      </span>
    </template>
    <template #description>
      <span>No files</span>
    </template>
  </AEmpty>
</template>

<style scoped>
@reference "../../styles/index.css";

.knowledge-file-list {
  @apply min-h-0;
}

.knowledge-file-list :deep(.ant-list-items) {
  @apply grid;

  gap: 0.25rem;
}

.knowledge-file-list-empty {
  @apply grid place-content-center;

  min-height: 12rem;
  margin: 0;
  color: var(--color-text-subtle);
}

.knowledge-file-list-empty :deep(.ant-empty-image) {
  @apply grid place-items-center;

  height: auto;
  margin-bottom: 0.9rem;
  color: var(--color-text-muted);
}

.knowledge-file-list-empty-mark {
  @apply grid place-items-center;

  width: 3.4rem;
  height: 3.4rem;
  border: 1px solid var(--color-border-control);
  border-radius: var(--radius-knowledge-container);
  color: var(--color-text-muted);
  background: var(--color-surface);
}

.knowledge-file-list-empty :deep(.ant-empty-description) {
  color: var(--color-text-muted);
}
</style>
