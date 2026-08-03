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
      <Files :size="25" :stroke-width="1.5" aria-hidden="true" />
    </template>
    <template #description>
      <span>No files</span>
    </template>
  </AEmpty>
</template>

<style scoped>
@reference "../styles/index.css";

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

  height: 2.25rem;
  margin-bottom: 0.45rem;
  color: var(--color-text-muted);
}

.knowledge-file-list-empty :deep(.ant-empty-description) {
  color: var(--color-text-muted);
  font-size: 0.88rem;
}
</style>
