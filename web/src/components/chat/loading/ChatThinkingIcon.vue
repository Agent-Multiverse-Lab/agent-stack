<script setup lang="ts">
const pixelDelays = Array.from({ length: 9 }, (_, index) => {
  const row = Math.floor(index / 3)
  const column = index % 3
  return (column + Math.abs(row - 1)) * 90
})
</script>

<template>
  <span
    class="grid shrink-0 grid-cols-[repeat(3,4px)] gap-[1.5px]"
    aria-hidden="true"
  >
    <span
      v-for="(delay, index) in pixelDelays"
      :key="index"
      class="thinking-pixel size-1 rounded-[1px] bg-graphite"
      :style="{ animationDelay: `${delay}ms` }"
    />
  </span>
</template>

<style scoped>
.thinking-pixel {
  opacity: 0.15;
  animation: pixel-on 650ms ease-in-out infinite;
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

@media (prefers-reduced-motion: reduce) {
  .thinking-pixel {
    opacity: 0.55;
    animation: none;
  }
}
</style>
