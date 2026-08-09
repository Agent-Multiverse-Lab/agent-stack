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
    class="knowledge-file-list min-h-0"
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

  <AEmpty
    v-else
    class="knowledge-file-list-empty grid place-content-center min-h-48 m-0 text-graphite/58"
  >
    <template #image>
      <span
        class="grid place-items-center h-[3.4rem] w-[3.4rem] border border-graphite/16 rounded-[16px] text-slate bg-paper"
        aria-hidden="true"
      >
        <Files :size="25" :stroke-width="1.5" />
      </span>
    </template>
    <template #description>
      <span>No files</span>
    </template>
  </AEmpty>
</template>
