<script setup lang="ts">
import type { Component } from "vue"
import { Button as AButton } from "ant-design-vue"
import { ChevronRight } from "@lucide/vue"

const props = defineProps<{
  icon: Component
  label: string
  tone: "road-map" | "ppt" | "slides"
}>()

const emit = defineEmits<{
  activate: []
}>()
</script>

<template>
  <AButton
    class="knowledge-tool grid! h-[74px]! min-h-[74px]! w-full! min-w-0 items-center gap-2 overflow-hidden whitespace-normal! rounded-[16px]! border-transparent! py-2! pr-2! pl-3! text-left font-medium! text-graphite! shadow-none! [grid-template-columns:minmax(0,1fr)_auto] hover:border-graphite/22! hover:text-graphite! focus-visible:border-graphite/22! focus-visible:text-graphite!"
    :class="{
      'bg-[#edf4ff]! hover:bg-[#e2edff]! focus-visible:bg-[#e2edff]!':
        props.tone === 'road-map',
      'bg-[#fff1e8]! hover:bg-[#ffe7d8]! focus-visible:bg-[#ffe7d8]!':
        props.tone === 'ppt',
      'bg-[#f3efff]! hover:bg-[#eae3ff]! focus-visible:bg-[#eae3ff]!':
        props.tone === 'slides'
    }"
    @click="emit('activate')"
  >
    <span class="flex min-w-0 flex-col items-start justify-center gap-0.5 p-0">
      <span class="grid h-[18px] w-[18px] shrink-0 place-items-center [&>svg]:block" aria-hidden="true">
        <component
          :is="props.icon"
          :size="18"
          :stroke-width="1.8"
        />
      </span>
      <span class="block w-full overflow-hidden text-ellipsis whitespace-nowrap leading-4">{{ props.label }}</span>
    </span>

    <ChevronRight
      class="block h-4 w-4 text-slate"
      :size="16"
      :stroke-width="1.8"
      aria-hidden="true"
    />
  </AButton>
</template>
