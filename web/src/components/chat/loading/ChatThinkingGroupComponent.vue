<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, useSlots } from "vue"
import { ChevronDown } from "@lucide/vue"

import ChatThinkingIcon from "./ChatThinkingIcon.vue"

withDefaults(defineProps<{
  label?: string
}>(), {
  label: "Thinking"
})

const slots = useSlots()
const hasDetails = computed(() => Boolean(slots.default))
const expanded = ref(true)
const elapsedMs = ref(0)
const elapsed = computed(() => {
  const totalSeconds = elapsedMs.value / 1000
  if (totalSeconds < 60) return `${totalSeconds.toFixed(1)}s`
  return `${Math.floor(totalSeconds / 60)}m ${(totalSeconds % 60).toFixed(1)}s`
})

let timer: number | undefined

onMounted(() => {
  const startedAt = performance.now()
  timer = window.setInterval(() => {
    elapsedMs.value = performance.now() - startedAt
  }, 100)
})

onBeforeUnmount(() => {
  if (timer !== undefined) window.clearInterval(timer)
})
</script>

<template>
  <section class="w-full max-w-[38rem]">
    <div
      class="flex w-fit items-center gap-2.5 py-1"
      role="status"
      aria-live="polite"
    >
      <ChatThinkingIcon />

      <span class="loading-label text-[13px] font-medium">
        {{ label }}
      </span>
      <span
        class="font-utility text-xs text-slate tabular-nums"
        aria-hidden="true"
      >
        {{ elapsed }}
      </span>
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
    </div>

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

<style scoped>
.loading-label {
  color: transparent;
  background-image: linear-gradient(
    90deg,
    var(--color-slate) 35%,
    var(--color-graphite) 50%,
    var(--color-slate) 65%
  );
  background-size: 200% 100%;
  background-clip: text;
  animation: shimmer-text 1.4s linear infinite;
}

@keyframes shimmer-text {
  from {
    background-position: 100% 0;
  }

  to {
    background-position: -100% 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .loading-label {
    color: var(--color-graphite);
    background-image: none;
    animation: none;
  }
}
</style>
