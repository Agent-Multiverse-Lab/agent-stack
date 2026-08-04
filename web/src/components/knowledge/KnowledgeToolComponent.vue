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
    class="knowledge-tool"
    :class="`is-${props.tone}`"
    @click="emit('activate')"
  >
    <span class="knowledge-tool-details">
      <span class="knowledge-tool-icon" aria-hidden="true">
        <component
          :is="props.icon"
          :size="18"
          :stroke-width="1.8"
        />
      </span>
      <span class="knowledge-tool-label">{{ props.label }}</span>
    </span>

    <ChevronRight
      class="knowledge-tool-chevron"
      :size="16"
      :stroke-width="1.8"
      aria-hidden="true"
    />
  </AButton>
</template>

<style scoped>
@reference "../../styles/index.css";

.knowledge-tool {
  @apply grid w-full min-w-0 items-center overflow-hidden text-left;

  box-sizing: border-box;
  grid-template-columns: minmax(0, 1fr) auto;
  height: 74px;
  min-height: 74px;
  gap: 8px;
  padding: 8px 8px 8px 12px;
  border-color: transparent;
  border-radius: var(--radius-knowledge-container);
  color: var(--color-text);
  background: var(--color-knowledge-tool-road-map);
  box-shadow: none;
  font-weight: 500;
  white-space: normal;
}

.knowledge-tool:hover,
.knowledge-tool:focus-visible {
  border-color: var(--color-border-focus);
  color: var(--color-text) !important;
  background: var(--color-knowledge-tool-road-map-hover) !important;
}

.knowledge-tool.is-ppt {
  background: var(--color-knowledge-tool-ppt);
}

.knowledge-tool.is-ppt:hover,
.knowledge-tool.is-ppt:focus-visible {
  background: var(--color-knowledge-tool-ppt-hover) !important;
}

.knowledge-tool.is-slides {
  background: var(--color-knowledge-tool-slides);
}

.knowledge-tool.is-slides:hover,
.knowledge-tool.is-slides:focus-visible {
  background: var(--color-knowledge-tool-slides-hover) !important;
}

.knowledge-tool-details {
  @apply flex min-w-0 flex-col items-start justify-center;

  gap: 2px;
  padding: 0;
}

.knowledge-tool-icon {
  @apply grid shrink-0 place-items-center;

  width: 18px;
  height: 18px;
}

.knowledge-tool-icon :deep(svg) {
  display: block;
}

.knowledge-tool-label {
  @apply block w-full overflow-hidden text-ellipsis whitespace-nowrap;

  line-height: 16px;
}

.knowledge-tool-chevron {
  display: block;
  width: 16px;
  height: 16px;
  color: var(--color-text-muted);
}
</style>
