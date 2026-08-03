<script setup lang="ts">
import { computed, ref } from "vue"
import {
  Button as AButton,
  Drawer as ADrawer,
  InputSearch as AInputSearch
} from "ant-design-vue"
import { X } from "@lucide/vue"

import type {
  KnowledgeFileItem,
  KnowledgePanelPresentation
} from "@/types/knowledge"

import KnowledgeFileAddComponent from "./KnowledgeFileAddComponent.vue"
import KnowledgeFileListComponent from "./KnowledgeFileListComponent.vue"

const props = defineProps<{
  files: KnowledgeFileItem[]
  selectedFileId: string | null
  presentation: KnowledgePanelPresentation
  open: boolean
}>()

const emit = defineEmits<{
  "files-selected": [files: File[]]
  select: [fileId: string]
  remove: [fileId: string]
  close: []
}>()

const searchQuery = ref("")

const visibleFiles = computed(() => {
  const query = searchQuery.value.trim().toLocaleLowerCase()
  if (!query) return props.files

  return props.files.filter((file) =>
    file.name.toLocaleLowerCase().includes(query)
  )
})

const regionComponent = computed(() =>
  props.presentation === "drawer" ? ADrawer : "section"
)

const regionBindings = computed<Record<string, unknown>>(() => {
  if (props.presentation === "panel") return {}

  return {
    open: props.open,
    placement: "left",
    width: "min(23rem, calc(100vw - 1rem))",
    closable: false,
    keyboard: true,
    maskClosable: true,
    destroyOnClose: false,
    role: "dialog",
    "aria-modal": "true",
    "aria-labelledby": "knowledge-files-title",
    rootClassName: "knowledge-files-drawer",
    onClose: () => emit("close"),
    onAfterOpenChange: restoreTriggerFocus
  }
})

/** 抽屉关闭后将键盘焦点归还给文件入口。 */
function restoreTriggerFocus(open: boolean) {
  if (open || props.presentation !== "drawer") return

  document.querySelector<HTMLElement>("#knowledge-files-trigger")?.focus()
}
</script>

<template>
  <component
    :is="regionComponent"
    v-bind="regionBindings"
    class="knowledge-files-host"
  >
    <div
      id="knowledge-files-region"
      class="knowledge-files"
      :class="{ 'is-drawer': props.presentation === 'drawer' }"
      tabindex="-1"
    >
      <header class="knowledge-files-header">
        <h2 id="knowledge-files-title">Files</h2>
        <AButton
          v-if="props.presentation === 'drawer'"
          class="knowledge-panel-close"
          type="text"
          shape="circle"
          aria-label="Close files"
          @click="emit('close')"
        >
          <X :size="18" :stroke-width="1.8" aria-hidden="true" />
        </AButton>
      </header>

      <div class="knowledge-files-body">
        <KnowledgeFileAddComponent
          @files-selected="emit('files-selected', $event)"
        />

        <AInputSearch
          v-model:value="searchQuery"
          class="knowledge-file-search"
          allow-clear
          aria-label="Search files"
          placeholder="Search files"
        />

        <div class="knowledge-files-list-region">
          <KnowledgeFileListComponent
            :files="visibleFiles"
            :selected-file-id="props.selectedFileId"
            @select="emit('select', $event)"
            @remove="emit('remove', $event)"
          />
        </div>
      </div>
    </div>
  </component>
</template>

<style scoped>
@reference "../styles/index.css";

.knowledge-files-host {
  @apply min-h-0 min-w-0;
}

.knowledge-files {
  @apply grid h-full min-h-0 min-w-0 overflow-hidden border;

  grid-template-rows: auto minmax(0, 1fr);
  border-color: var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
}

.knowledge-files:focus-visible {
  outline-offset: -3px;
}

.knowledge-files-header {
  @apply flex min-w-0 items-center justify-between;

  min-height: 4.5rem;
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--color-border-subtle);
}

.knowledge-files-header h2 {
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

.knowledge-files-body {
  @apply grid min-h-0;

  grid-template-rows: auto auto minmax(0, 1fr);
  gap: 0.8rem;
  padding: 0.9rem;
}

.knowledge-file-search :deep(.ant-input-affix-wrapper) {
  min-height: 2.4rem;
  border-color: var(--color-border-control);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  box-shadow: none;
}

.knowledge-file-search :deep(.ant-input-affix-wrapper:hover),
.knowledge-file-search :deep(.ant-input-affix-wrapper-focused) {
  border-color: var(--color-border-focus);
}

.knowledge-file-search :deep(.ant-input) {
  color: var(--color-text);
  font-size: 0.85rem;
}

.knowledge-file-search :deep(.ant-input::placeholder) {
  color: var(--color-text-subtle);
}

.knowledge-files-list-region {
  @apply min-h-0 overflow-y-auto overscroll-contain;
}

:global(.knowledge-files-drawer .ant-drawer-content) {
  background: var(--color-surface-muted);
}

:global(.knowledge-files-drawer .ant-drawer-body) {
  padding: 0.65rem;
}

.knowledge-files.is-drawer {
  min-height: calc(100dvh - 1.3rem);
}

@media (max-width: 720px) {
  .knowledge-file-search :deep(.ant-input) {
    font-size: 1rem;
  }
}
</style>
