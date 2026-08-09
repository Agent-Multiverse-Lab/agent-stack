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
    class="grid min-w-0 items-center gap-[0.15rem] min-h-14 py-[0.3rem] pr-[0.35rem] pl-[0.5rem] border border-transparent rounded-[16px] transition-colors duration-120 hover:bg-mist [grid-template-columns:minmax(0,1fr)_auto]"
    :class="{ 'border-graphite/16 bg-graphite/6': props.selected }"
  >
    <button
      class="grid min-w-0 items-center gap-[0.55rem] border-0 bg-transparent p-0 text-left [grid-template-columns:auto_minmax(0,1fr)]"
      type="button"
      :aria-current="props.selected ? 'true' : undefined"
      @click="emit('select', props.file.id)"
    >
      <span
        class="grid shrink-0 place-items-center h-8 w-8 border border-graphite/10 rounded-[16px] text-slate bg-paper"
        :class="{ 'text-paper bg-graphite': props.selected }"
        aria-hidden="true"
      >
        <FileText :size="17" :stroke-width="1.7" />
      </span>

      <span class="min-w-0">
        <strong
          class="overflow-hidden text-ellipsis whitespace-nowrap font-medium"
          :title="props.file.name"
        >
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
