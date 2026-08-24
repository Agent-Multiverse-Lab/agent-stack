<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue"

withDefaults(defineProps<{
  label?: string
}>(), {
  label: "Thinking"
})

const pixelDelays = Array.from({ length: 9 }, (_, index) => {
  const row = Math.floor(index / 3)
  const column = index % 3
  return (column + Math.abs(row - 1)) * 90
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
    <span
      class="grid shrink-0 grid-cols-[repeat(3,4px)] gap-[1.5px]"
      aria-hidden="true"
    >
      <span
        v-for="(delay, index) in pixelDelays"
        :key="index"
        class="loading-pixel size-1 rounded-[1px] bg-graphite"
        :style="{ animationDelay: `${delay}ms` }"
      />
    </span>

    <span class="loading-label text-[13px] font-medium">
      {{ label }}
    </span>
    <span
      class="font-utility text-xs text-slate tabular-nums"
      aria-hidden="true"
    >
      {{ elapsed }}
    </span>
  </div>
</template>

<style scoped>
.loading-pixel {
  opacity: 0.15;
  animation: pixel-on 650ms ease-in-out infinite;
}

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

@keyframes pixel-on {
  0%,
  100% {
    opacity: 0.15;
  }

  45% {
    opacity: 0.95;
  }
}

@keyframes shimmer-text {
  from {
    background-position: 100% 0;
  }

  to {
    background-position: -100% 0;
  }
}
</style>
