<script setup lang="ts">
import { computed } from "vue"
import { XIcon } from "@lucide/vue"
import ChatTrajectoryComponent from "./ChatTrajectoryComponent.vue"
import ChatAttachmentDetailsComponent from "./ChatAttachmentDetailsComponent.vue"

const props = defineProps<{
  type: 'none' | 'trajectory' | 'attachment'
  id?: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const title = computed(() => {
  if (props.type === 'trajectory') return 'Agent Activity'
  if (props.type === 'attachment') return 'Attachment Details'
  return 'Activity'
})
</script>

<template>
  <aside class="flex w-[22rem] shrink-0 flex-col border-l border-surface bg-paper lg:w-[24rem]">
    <!-- Header -->
    <header class="flex h-14 shrink-0 items-center justify-between border-b border-surface px-4">
      <h2 class="text-sm font-medium text-graphite">{{ title }}</h2>
      <button
        type="button"
        class="inline-flex size-8 items-center justify-center rounded-md text-slate hover:bg-surface hover:text-graphite transition-colors"
        @click="emit('close')"
        title="Close panel"
      >
        <XIcon class="size-4" />
      </button>
    </header>
    
    <!-- Content Area -->
    <div class="flex-1 overflow-y-auto overscroll-contain p-4">
      <ChatTrajectoryComponent 
        v-if="type === 'trajectory'" 
        :run-id="id" 
      />
      <ChatAttachmentDetailsComponent 
        v-else-if="type === 'attachment'" 
        :file-id="id" 
      />
    </div>
  </aside>
</template>
