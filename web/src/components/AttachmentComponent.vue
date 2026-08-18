<script setup lang="ts">
import { computed } from "vue"
import { File as FileIcon, X } from "@lucide/vue"
import { Tooltip as ATooltip } from "ant-design-vue"

import type { ChatAttachment } from "@/types/attachment"

const props = defineProps<{
  attachment: ChatAttachment
  removable?: boolean
}>()

const emit = defineEmits<{
  remove: [fileId: string]
}>()

const isImage = computed(() =>
  props.attachment.content_type.startsWith("image/") &&
  Boolean(props.attachment.access_url)
)
</script>

<template>
  <li
    class="grid h-11 max-w-[17rem] min-w-0 shrink-0 items-center gap-2 rounded-full border border-graphite/12 bg-paper p-1 text-graphite"
    :class="removable
      ? 'grid-cols-[2rem_minmax(0,1fr)_2rem]'
      : 'grid-cols-[2rem_minmax(0,1fr)] pr-3'"
  >
    <span
      class="grid size-8 shrink-0 place-items-center overflow-hidden rounded-full bg-graphite/6 text-slate"
      aria-hidden="true"
    >
      <img
        v-if="isImage"
        class="size-full object-cover"
        :src="props.attachment.access_url ?? undefined"
        alt=""
      >
      <FileIcon
        v-else
        :size="15"
        :stroke-width="1.8"
      />
    </span>

    <strong
      class="min-w-0 truncate font-medium text-sm"
      :title="props.attachment.file_name"
    >
      {{ props.attachment.file_name }}
    </strong>

    <ATooltip
      v-if="removable"
      placement="top"
      :title="`Remove ${props.attachment.file_name}`"
    >
      <button
        class="grid size-7 shrink-0 place-items-center rounded-full bg-transparent text-graphite/58 transition-colors duration-120 hover:bg-graphite hover:text-paper motion-reduce:transition-none"
        type="button"
        :aria-label="`Remove attachment ${props.attachment.file_name}`"
        @click="emit('remove', props.attachment.file_id)"
      >
        <X
          :size="14"
          :stroke-width="1.9"
          aria-hidden="true"
        />
      </button>
    </ATooltip>
  </li>
</template>
