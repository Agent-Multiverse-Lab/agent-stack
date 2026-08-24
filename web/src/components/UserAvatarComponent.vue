<script setup lang="ts">
import { computed } from "vue"

const props = withDefaults(defineProps<{
  label?: string
  size?: "small" | "large"
}>(), {
  label: "AM User",
  size: "small"
})

const initial = computed(() =>
  props.label.trim().charAt(0).toUpperCase() || "A"
)
</script>

<template>
  <span
    class="inline-grid shrink-0 place-items-center rounded-full bg-graphite font-utility font-bold leading-none text-paper select-none"
    :class="size === 'large' ? 'size-14 text-lg' : 'size-7 text-[11px]'"
    aria-hidden="true"
  >
    {{ initial }}
  </span>
</template>
