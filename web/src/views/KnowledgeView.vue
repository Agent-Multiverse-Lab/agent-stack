<script setup lang="ts">
import {
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref
} from "vue"
import { useRouter } from "vue-router"

import KnowledgeChatComponent from "@/components/KnowledgeChatComponent.vue"
import KnowledgeFileActionsComponent from "@/components/KnowledgeFileActionsComponent.vue"
import KnowledgeFilesComponent from "@/components/KnowledgeFilesComponent.vue"
import KnowledgeNavigationComponent from "@/components/KnowledgeNavigationComponent.vue"
import type { KnowledgeFileItem } from "@/types/knowledge"

type OpenKnowledgeDrawer = "files" | "actions" | null

const router = useRouter()

const files = ref<KnowledgeFileItem[]>([])
const selectedFileId = ref<string | null>(null)
const compactMode = ref(false)
const openDrawer = ref<OpenKnowledgeDrawer>(null)

let compactViewportQuery: MediaQueryList | null = null

/** 生成只用于本地页面状态的文件标识。 */
function createLocalFileId(): string {
  return crypto.randomUUID()
}

/** 将浏览器文件选择结果转换为知识页的本地文件记录。 */
function createKnowledgeFile(file: File): KnowledgeFileItem {
  const extension = file.name.split(".").pop()?.toLocaleUpperCase() || "FILE"

  return {
    id: createLocalFileId(),
    source: file,
    name: file.name,
    size: file.size,
    mimeType: file.type,
    extension,
    lastModified: file.lastModified,
    status: "local"
  }
}

/** 合并新选择的本地文件，并保持当前选择稳定。 */
function addLocalFiles(selectedFiles: File[]) {
  const existingFiles = new Set(
    files.value.map((file) =>
      [file.name, file.size, file.lastModified].join(":")
    )
  )
  const additions = selectedFiles
    .filter(
      (file) =>
        !existingFiles.has([file.name, file.size, file.lastModified].join(":"))
    )
    .map(createKnowledgeFile)

  if (!additions.length) return

  files.value.push(...additions)
  selectedFileId.value ??= additions[0]?.id ?? null
}

/** 从本地文件集合移除一项，并选择最接近的剩余文件。 */
function removeLocalFile(fileId: string) {
  const fileIndex = files.value.findIndex((file) => file.id === fileId)
  if (fileIndex < 0) return

  files.value.splice(fileIndex, 1)

  if (selectedFileId.value !== fileId) return

  selectedFileId.value =
    files.value[fileIndex]?.id ?? files.value[fileIndex - 1]?.id ?? null

  if (!selectedFileId.value) openDrawer.value = null
}

/** 同步桌面与抽屉布局，并阻止两个抽屉重叠。 */
function updateCompactMode(event?: MediaQueryListEvent) {
  compactMode.value =
    event?.matches ?? compactViewportQuery?.matches ?? false

  if (!compactMode.value) openDrawer.value = null
}

/** 聚焦桌面区域，或在紧凑布局中打开对应抽屉。 */
async function openRegion(
  region: Exclude<OpenKnowledgeDrawer, null>,
  elementId: string
) {
  if (compactMode.value) {
    openDrawer.value = region
    return
  }

  await nextTick()
  document.querySelector<HTMLElement>(`#${elementId}`)?.focus()
}

/** 关闭侧栏抽屉并将焦点送回知识对话区。 */
async function focusChat() {
  openDrawer.value = null
  await nextTick()
  document.querySelector<HTMLElement>("#knowledge-chat-region")?.focus()
}

/** 返回常驻导航中的新对话页面。 */
async function returnToChat() {
  await router.push({ name: "chat" })
}

onMounted(() => {
  compactViewportQuery = window.matchMedia("(max-width: 1279px)")
  updateCompactMode()
  compactViewportQuery.addEventListener("change", updateCompactMode)
})

onBeforeUnmount(() => {
  compactViewportQuery?.removeEventListener("change", updateCompactMode)
})
</script>

<template>
  <main class="knowledge-view">
    <KnowledgeNavigationComponent
      :compact-mode="compactMode"
      :files-open="openDrawer === 'files'"
      :actions-open="openDrawer === 'actions'"
      @back="returnToChat"
      @files="openRegion('files', 'knowledge-files-region')"
      @chat="focusChat"
      @actions="openRegion('actions', 'knowledge-actions-region')"
    />

    <KnowledgeFilesComponent
      :files="files"
      :selected-file-id="selectedFileId"
      :presentation="compactMode ? 'drawer' : 'panel'"
      :open="openDrawer === 'files'"
      @files-selected="addLocalFiles"
      @select="selectedFileId = $event"
      @remove="removeLocalFile"
      @close="openDrawer = null"
    />

    <KnowledgeChatComponent
      :files="files"
    />

    <KnowledgeFileActionsComponent
      :presentation="compactMode ? 'drawer' : 'panel'"
      :open="openDrawer === 'actions'"
      @close="openDrawer = null"
    />
  </main>
</template>

<style scoped>
@reference "../styles/index.css";

.knowledge-view {
  @apply grid h-dvh w-full min-h-0 min-w-0 overflow-hidden;

  grid-template-columns:
    4.5rem
    minmax(0, 2fr)
    minmax(0, 5fr)
    minmax(0, 2fr);
  gap: 0.75rem;
  padding: 0.75rem;
  color: var(--color-text);
  background: var(--color-surface-muted);
}

@media (max-width: 1279px) {
  .knowledge-view {
    grid-template-columns: 4.5rem minmax(0, 1fr);
  }
}

@media (max-width: 720px) {
  .knowledge-view {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: auto minmax(0, 1fr);
    gap: 0;
    padding: 0;
    background: var(--color-surface);
  }
}
</style>
