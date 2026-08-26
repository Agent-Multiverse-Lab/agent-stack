<script setup lang="ts">
import { computed, ref, useSlots } from "vue"
import { ChevronDown } from "@lucide/vue"

import ChatLoadingStateComponent from "./ChatLoadingStateComponent.vue"

withDefaults(defineProps<{
  label?: string
}>(), {
  label: "Thinking"
})

const slots = useSlots()
const hasDetails = computed(() => Boolean(slots.default))
const expanded = ref(true)
</script>

<template>
  <section class="w-full max-w-[38rem]">
    <ChatLoadingStateComponent :label="label">
      <template #trailing>
        <button
          v-if="hasDetails"
          type="button"
          class="grid size-7 place-items-center rounded-full text-slate transition-colors duration-150 hover:bg-mist hover:text-graphite motion-reduce:transition-none"
          :aria-expanded="expanded"
          :aria-label="expanded ? 'Collapse thinking details' : 'Expand thinking details'"
          @click="expanded = !expanded"
        >
          <ChevronDown
            class="transition-transform duration-200 motion-reduce:transition-none"
            :class="{ 'rotate-180': expanded }"
            :size="16"
            :stroke-width="1.8"
            aria-hidden="true"
          />
        </button>
      </template>
    </ChatLoadingStateComponent>

    <Transition
      enter-active-class="transition-[opacity,transform] duration-200 ease-out motion-reduce:transition-none"
      leave-active-class="transition-[opacity,transform] duration-150 ease-in motion-reduce:transition-none"
      enter-from-class="-translate-y-1 opacity-0 motion-reduce:translate-y-0"
      leave-to-class="-translate-y-1 opacity-0 motion-reduce:translate-y-0"
    >
      <div
        v-if="hasDetails && expanded"
        class="relative mt-1 ml-[5px] min-w-0 border-l border-graphite/12 py-1 pl-5"
      >
        <slot />
      </div>
    </Transition>
  </section>
</template>
