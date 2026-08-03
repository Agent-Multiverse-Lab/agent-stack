<script setup lang="ts">
import { computed, type Component } from "vue"
import {
  Button as AButton,
  Drawer as ADrawer,
  message
} from "ant-design-vue"
import {
  Map,
  PanelsTopLeft,
  Presentation,
  X
} from "@lucide/vue"

import type { KnowledgePanelPresentation } from "@/types/knowledge"

const props = defineProps<{
  presentation: KnowledgePanelPresentation
  open: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const tools: Array<{
  id: string
  label: string
  icon: Component
}> = [
  { id: "road-map", label: "Road Map", icon: Map },
  { id: "ppt", label: "PPT", icon: Presentation },
  { id: "slides", label: "Slides", icon: PanelsTopLeft }
]

const regionComponent = computed(() =>
  props.presentation === "drawer" ? ADrawer : "section"
)

const regionBindings = computed<Record<string, unknown>>(() => {
  if (props.presentation === "panel") return {}

  return {
    open: props.open,
    placement: "right",
    width: "min(23rem, calc(100vw - 1rem))",
    closable: false,
    keyboard: true,
    maskClosable: true,
    destroyOnClose: false,
    role: "dialog",
    "aria-modal": "true",
    "aria-labelledby": "knowledge-actions-title",
    rootClassName: "knowledge-actions-drawer",
    onClose: () => emit("close"),
    onAfterOpenChange: restoreTriggerFocus
  }
})

/** 抽屉关闭后将键盘焦点归还给工具入口。 */
function restoreTriggerFocus(open: boolean) {
  if (open || props.presentation !== "drawer") return

  document.querySelector<HTMLElement>("#knowledge-actions-trigger")?.focus()
}

/** 明确提示样例功能尚未连接生成服务。 */
function openTool(label: string) {
  void message.info(`${label} is not connected yet.`)
}
</script>

<template>
  <component
    :is="regionComponent"
    v-bind="regionBindings"
    class="knowledge-actions-host"
  >
    <div
      id="knowledge-actions-region"
      class="knowledge-actions"
      :class="{ 'is-drawer': props.presentation === 'drawer' }"
      tabindex="-1"
    >
      <header class="knowledge-actions-header">
        <h2 id="knowledge-actions-title">Tools</h2>
        <AButton
          v-if="props.presentation === 'drawer'"
          class="knowledge-panel-close"
          type="text"
          shape="circle"
          aria-label="Close tools"
          @click="emit('close')"
        >
          <X :size="18" :stroke-width="1.8" aria-hidden="true" />
        </AButton>
      </header>

      <div class="knowledge-actions-body">
        <AButton
          v-for="tool in tools"
          :key="tool.id"
          class="knowledge-tool"
          @click="openTool(tool.label)"
        >
          <component
            :is="tool.icon"
            :size="24"
            :stroke-width="1.7"
            aria-hidden="true"
          />
          <span>{{ tool.label }}</span>
        </AButton>
      </div>
    </div>
  </component>
</template>

<style scoped>
@reference "../styles/index.css";

.knowledge-actions-host {
  @apply min-h-0 min-w-0;
}

.knowledge-actions {
  @apply grid h-full min-h-0 min-w-0 overflow-hidden border;

  grid-template-rows: auto minmax(0, 1fr);
  border-color: var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
}

.knowledge-actions:focus-visible {
  outline-offset: -3px;
}

.knowledge-actions-header {
  @apply flex min-w-0 items-center justify-between;

  min-height: 4.5rem;
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--color-border-subtle);
}

.knowledge-actions-header h2 {
  @apply m-0 font-semibold;

  font-size: 1rem;
  letter-spacing: -0.025em;
}

.knowledge-panel-close {
  @apply grid shrink-0 place-items-center;

  width: 2.75rem;
  min-width: 2.75rem;
  height: 2.75rem;
  color: var(--color-text-muted);
}

.knowledge-panel-close:hover,
.knowledge-panel-close:focus-visible {
  color: var(--color-text);
  background: var(--color-surface-hover);
}

.knowledge-actions-body {
  @apply grid min-h-0 content-start overflow-y-auto overscroll-contain;

  gap: 0.65rem;
  padding: 0.9rem;
}

.knowledge-tool {
  @apply flex w-full items-center justify-start;

  min-height: 4.75rem;
  gap: 0.85rem;
  padding-inline: 1rem;
  border-color: var(--color-border-control);
  border-radius: var(--radius-md);
  color: var(--color-text);
  background: var(--color-surface);
  box-shadow: none;
  font-size: 0.9rem;
  font-weight: 600;
}

.knowledge-tool:hover,
.knowledge-tool:focus-visible {
  border-color: var(--color-border-focus) !important;
  color: var(--color-text) !important;
  background: var(--color-surface-hover) !important;
}

.knowledge-tool :deep(svg) {
  @apply shrink-0;
}

:global(.knowledge-actions-drawer .ant-drawer-content) {
  background: var(--color-surface-muted);
}

:global(.knowledge-actions-drawer .ant-drawer-body) {
  padding: 0.65rem;
}

.knowledge-actions.is-drawer {
  min-height: calc(100dvh - 1.3rem);
}
</style>
