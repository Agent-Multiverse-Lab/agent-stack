<script setup lang="ts">
import { computed, h, ref, watch } from "vue"
import {
  Button as AButton,
  Drawer as ADrawer,
  Input as AInput,
  message,
  Upload,
  UploadDragger,
  type UploadProps
} from "ant-design-vue"
import {
  Globe,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  TriangleAlert,
  X
} from "@lucide/vue"

import type {
  KnowledgeFileItem,
  KnowledgePanelPresentation
} from "@/types/knowledge"

import KnowledgeFileListComponent from "./KnowledgeFileListComponent.vue"

const props = defineProps<{
  files: KnowledgeFileItem[]
  selectedFileId: string | null
  collapsed: boolean
  presentation: KnowledgePanelPresentation
  open: boolean
}>()

const emit = defineEmits<{
  "files-selected": [files: File[]]
  select: [fileId: string]
  remove: [fileId: string]
  close: []
  "toggle-collapse": []
}>()

const acceptedExtensions = new Set([
  "pdf",
  "doc",
  "docx",
  "txt",
  "md",
  "markdown",
  "csv",
  "xls",
  "xlsx",
  "ppt",
  "pptx",
  "png",
  "jpg",
  "jpeg",
  "webp"
])

const searchQuery = ref("")
const appliedSearchQuery = ref("")

const visibleFiles = computed(() => {
  const query = appliedSearchQuery.value.toLocaleLowerCase()
  if (!query) return props.files

  return props.files.filter((file) =>
    file.name.toLocaleLowerCase().includes(query)
  )
})

watch(searchQuery, (query) => {
  if (!query.trim()) appliedSearchQuery.value = ""
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

/** 接收本地文件，但阻止组件发起尚未接通的上传请求。 */
const selectLocalFile: UploadProps["beforeUpload"] = (file) => {
  const extension = file.name.split(".").pop()?.toLocaleLowerCase() ?? ""
  if (!acceptedExtensions.has(extension)) {
    void message.warning({
      content: `${file.name} is not a supported source type.`,
      icon: h(TriangleAlert, {
        size: 16,
        strokeWidth: 1.8,
        "aria-hidden": "true"
      })
    })
    return Upload.LIST_IGNORE
  }

  emit("files-selected", [file as File])
  return Upload.LIST_IGNORE
}

/** 提交当前输入，并按文件名更新列表过滤条件。 */
function submitSearch() {
  const query = searchQuery.value.trim()
  if (!query) return

  appliedSearchQuery.value = query
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
      :class="{
        'is-collapsed': props.presentation === 'panel' && props.collapsed,
        'is-drawer': props.presentation === 'drawer'
      }"
      tabindex="-1"
    >
      <header class="knowledge-files-header">
        <h2 id="knowledge-files-title">Files</h2>
        <AButton
          v-if="props.presentation === 'panel'"
          class="knowledge-panel-collapse"
          type="text"
          shape="circle"
          :aria-label="props.collapsed ? 'Expand files' : 'Collapse files'"
          :aria-expanded="!props.collapsed"
          aria-controls="knowledge-files-body"
          :title="props.collapsed ? 'Expand files' : 'Collapse files'"
          @click="emit('toggle-collapse')"
        >
          <span class="knowledge-panel-collapse-icon" aria-hidden="true">
            <PanelLeftOpen
              v-if="props.collapsed"
              :size="18"
              :stroke-width="1.8"
            />
            <PanelLeftClose
              v-else
              :size="18"
              :stroke-width="1.8"
            />
          </span>
        </AButton>
        <AButton
          v-else
          class="knowledge-panel-close"
          type="text"
          shape="circle"
          aria-label="Close files"
          @click="emit('close')"
        >
          <X :size="18" :stroke-width="1.8" aria-hidden="true" />
        </AButton>
      </header>

      <div id="knowledge-files-body" class="knowledge-files-body">
        <UploadDragger
          class="knowledge-file-add"
          name="knowledge-file"
          accept=".pdf,.doc,.docx,.txt,.md,.markdown,.csv,.xls,.xlsx,.ppt,.pptx,.png,.jpg,.jpeg,.webp"
          multiple
          :before-upload="selectLocalFile"
          :show-upload-list="false"
        >
          <div class="knowledge-file-add-content">
            <span class="knowledge-file-add-icon" aria-hidden="true">
              <Plus :size="18" :stroke-width="1.8" />
            </span>
            <strong class="knowledge-file-add-copy">Add Sources</strong>
          </div>
        </UploadDragger>

        <form
          class="knowledge-file-search"
          role="search"
          @submit.prevent="submitSearch"
        >
          <AInput
            v-model:value="searchQuery"
            class="knowledge-file-search-input"
            type="text"
            inputmode="text"
            :bordered="false"
            aria-label="Search files"
            placeholder="Search files"
          />

          <div class="knowledge-file-search-actions">
            <span class="knowledge-file-search-web-mark" aria-hidden="true">
              <Globe :size="18" :stroke-width="1.8" />
            </span>

            <AButton
              class="knowledge-file-search-submit"
              type="primary"
              shape="circle"
              html-type="submit"
              aria-label="Search"
            >
              <Search :size="18" :stroke-width="2" aria-hidden="true" />
            </AButton>
          </div>
        </form>

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
@reference "../../styles/index.css";

.knowledge-files-host {
  @apply min-h-0 min-w-0;
}

.knowledge-files {
  @apply grid h-full min-h-0 min-w-0 overflow-hidden border;

  grid-template-rows: 48px minmax(0, 1fr);
  caret-color: transparent;
  border-color: var(--color-border);
  border-radius: var(--radius-knowledge-container);
  background: var(--color-surface);
}

.knowledge-files:focus-visible {
  outline-offset: -3px;
}

.knowledge-files-header {
  @apply flex min-w-0 items-center justify-between;

  box-sizing: border-box;
  height: 48px;
  min-height: 48px;
  max-height: 48px;
  padding-inline: 16px;
  border-bottom: 1px solid var(--color-border-subtle);
  user-select: none;
  caret-color: transparent;
  transition: padding-inline 240ms cubic-bezier(0.65, 0, 0.35, 1);
}

.knowledge-files-header h2 {
  @apply m-0 min-w-0 flex-1 overflow-hidden whitespace-nowrap font-semibold;

  opacity: 1;
  visibility: visible;
  user-select: none;
  caret-color: transparent;
  cursor: default;
  font-size: 1rem;
  letter-spacing: -0.025em;
  transition:
    opacity 140ms ease 100ms,
    visibility 0s linear;
}

.knowledge-panel-collapse {
  @apply grid shrink-0 place-items-center p-0;

  width: 40px;
  min-width: 40px;
  height: 40px;
  color: var(--color-text-muted);
}

.knowledge-panel-collapse:hover,
.knowledge-panel-collapse:focus-visible {
  color: var(--color-text);
  background: var(--color-surface-hover);
}

.knowledge-panel-collapse-icon {
  @apply grid place-items-center;

  width: 18px;
  height: 18px;
}

.knowledge-panel-collapse-icon :deep(svg) {
  display: block;
  width: 18px;
  height: 18px;
}

.knowledge-files.is-collapsed .knowledge-files-header {
  padding-inline: 7px;
}

.knowledge-files.is-collapsed .knowledge-files-header h2,
.knowledge-files.is-collapsed .knowledge-files-body {
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition:
    opacity 80ms ease,
    visibility 0s linear 80ms;
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
  @apply grid min-h-0 min-w-0;

  grid-template-rows: auto auto minmax(0, 1fr);
  gap: 0.8rem;
  padding: 0.9rem;
  opacity: 1;
  visibility: visible;
  transition:
    opacity 140ms ease 100ms,
    visibility 0s linear;
}

.knowledge-file-add {
  @apply block;
}

.knowledge-file-add :deep(.ant-upload-drag) {
  box-sizing: border-box;
  height: 48px;
  min-height: 48px;
  max-height: 48px;
  overflow: hidden;
  border: 1px dashed var(--color-border-control);
  border-radius: 96px;
  background: var(--color-surface-muted);
  transition:
    border-color 140ms ease,
    background-color 140ms ease;
}

.knowledge-file-add :deep(.ant-upload-drag:hover),
.knowledge-file-add :deep(.ant-upload-drag-hover) {
  border-color: var(--color-border-focus);
  background: var(--color-surface-emphasis);
}

.knowledge-file-add :deep(.ant-upload-btn) {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.65rem !important;
}

.knowledge-file-add-content {
  @apply flex items-center text-left;

  gap: 0.65rem;
}

.knowledge-file-add-icon {
  @apply grid shrink-0 place-items-center;

  width: 2.15rem;
  height: 2.15rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-knowledge-container);
  color: var(--color-text);
  background: var(--color-surface);
}

.knowledge-file-add-copy {
  @apply flex min-w-0 items-center self-stretch font-semibold;

  color: var(--color-text);
  line-height: 1;
  letter-spacing: -0.01em;
}

.knowledge-file-search {
  @apply grid min-w-0 border;

  grid-template-rows: minmax(2.4rem, auto) 2rem;
  gap: 0.25rem;
  padding: 0.45rem;
  border-color: var(--color-border-control);
  border-radius: var(--radius-knowledge-container);
  background: var(--color-surface);
  transition: border-color 140ms ease;
}

.knowledge-file-search:focus-within {
  border-color: var(--color-border-focus);
}

.knowledge-file-search-input.ant-input {
  min-width: 0;
  padding: 0.25rem 0.35rem;
  border: 0;
  user-select: text;
  caret-color: auto;
  color: var(--color-text);
  background: transparent;
  box-shadow: none;
}

.knowledge-file-search-input.ant-input:hover,
.knowledge-file-search-input.ant-input:focus {
  border: 0;
  background: transparent;
  box-shadow: none;
}

.knowledge-file-search-input.ant-input::placeholder {
  color: var(--color-text-subtle);
}

.knowledge-file-search-actions {
  @apply flex min-w-0 items-center justify-between;
}

.knowledge-file-search-web-mark {
  @apply grid shrink-0 place-items-center;

  width: 32px;
  height: 32px;
  color: var(--color-text-muted);
}

.knowledge-file-search-submit {
  @apply grid shrink-0 place-items-center p-0;

  width: 32px;
  min-width: 32px;
  height: 32px;
  border-color: var(--color-action-primary);
  color: var(--color-on-action);
  background: var(--color-action-primary);
  box-shadow: none;
}

.knowledge-file-search-submit:hover,
.knowledge-file-search-submit:focus-visible {
  border-color: var(--color-action-primary-hover);
  color: var(--color-on-action);
  background: var(--color-action-primary-hover);
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
  .knowledge-files.is-collapsed .knowledge-files-header {
    padding-inline: 16px;
  }

  .knowledge-files.is-collapsed .knowledge-files-header h2,
  .knowledge-files.is-collapsed .knowledge-files-body {
    opacity: 1;
    visibility: visible;
    pointer-events: auto;
    transition: none;
  }

  .knowledge-panel-collapse {
    display: none;
  }

  .knowledge-file-search-input.ant-input {
    font-size: 1rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  .knowledge-files-header,
  .knowledge-files-header h2,
  .knowledge-files-body {
    transition: none;
  }
}
</style>
