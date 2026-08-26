<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue"

import ChatThinkingIcon from "./ChatThinkingIcon.vue"

withDefaults(defineProps<{
  label?: string
}>(), {
  label: "Thinking"
})

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
    <slot name="trailing" />
  </div>
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
