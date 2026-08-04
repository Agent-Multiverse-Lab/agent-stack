<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from "vue"
import { gsap } from "gsap"

import KnowledgeChatComponent from "@/components/knowledge/KnowledgeChatComponent.vue"
import KnowledgeFileActionsComponent from "@/components/knowledge/KnowledgeFileActionsComponent.vue"
import KnowledgeFilesComponent from "@/components/knowledge/KnowledgeFilesComponent.vue"
import type { KnowledgeFileItem } from "@/types/knowledge"

const files = ref<KnowledgeFileItem[]>([])
const selectedFileId = ref<string | null>(null)
const filesCollapsed = ref(false)
const toolsCollapsed = ref(false)
const knowledgeView = ref<HTMLElement | null>(null)

let collapseMotionEnabled = false
let layoutTween: ReturnType<typeof gsap.fromTo> | null = null
let motionMatcher: ReturnType<typeof gsap.matchMedia> | null = null

/** 终止当前布局动画，并让 CSS 收纳状态重新接管列宽。 */
function clearLayoutTween() {
  layoutTween?.kill()
  layoutTween = null
  knowledgeView.value?.style.removeProperty("grid-template-columns")
}

/** 在状态切换前后读取真实列宽，并从当前画面过渡到最新布局。 */
async function animateLayoutChange(updateState: () => void) {
  const view = knowledgeView.value
  if (!view || !collapseMotionEnabled) {
    clearLayoutTween()
    updateState()
    return
  }

  const startColumns = getComputedStyle(view).gridTemplateColumns
  clearLayoutTween()
  updateState()
  await nextTick()

  if (knowledgeView.value !== view || !view.isConnected) return

  const endColumns = getComputedStyle(view).gridTemplateColumns
  if (startColumns === endColumns) return

  layoutTween = gsap.fromTo(
    view,
    { gridTemplateColumns: startColumns },
    {
      gridTemplateColumns: endColumns,
      duration: 0.24,
      ease: "power2.inOut",
      overwrite: "auto",
      onComplete: () => {
        view.style.removeProperty("grid-template-columns")
        layoutTween = null
      }
    }
  )
}

/** 切换 Files 面板的桌面收纳状态。 */
function toggleFilesCollapsed() {
  void animateLayoutChange(() => {
    filesCollapsed.value = !filesCollapsed.value
  })
}

/** 切换 Tools 面板的桌面收纳状态。 */
function toggleToolsCollapsed() {
  void animateLayoutChange(() => {
    toolsCollapsed.value = !toolsCollapsed.value
  })
}

onMounted(() => {
  motionMatcher = gsap.matchMedia()
  motionMatcher.add(
    {
      isDesktop: "(min-width: 721px)",
      reduceMotion: "(prefers-reduced-motion: reduce)"
    },
    (context) => {
      const conditions = context.conditions as {
        isDesktop: boolean
        reduceMotion: boolean
      }
      collapseMotionEnabled =
        conditions.isDesktop && !conditions.reduceMotion

      if (!collapseMotionEnabled) clearLayoutTween()

      return () => {
        collapseMotionEnabled = false
        clearLayoutTween()
      }
    }
  )
})

onUnmounted(() => {
  clearLayoutTween()
  motionMatcher?.revert()
  motionMatcher = null
})

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
}
</script>

<template>
  <main
    ref="knowledgeView"
    class="knowledge-view"
    :class="{
      'is-files-collapsed': filesCollapsed,
      'is-tools-collapsed': toolsCollapsed
    }"
  >
    <KnowledgeFilesComponent
      class="knowledge-view-files"
      :files="files"
      :selected-file-id="selectedFileId"
      :collapsed="filesCollapsed"
      presentation="panel"
      :open="false"
      @files-selected="addLocalFiles"
      @select="selectedFileId = $event"
      @remove="removeLocalFile"
      @toggle-collapse="toggleFilesCollapsed"
    />

    <KnowledgeChatComponent
      class="knowledge-view-chat"
      :files="files"
    />

    <KnowledgeFileActionsComponent
      class="knowledge-view-actions"
      :collapsed="toolsCollapsed"
      presentation="panel"
      :open="false"
      @toggle-collapse="toggleToolsCollapsed"
    />
  </main>
</template>

<style scoped>
@reference "../styles/index.css";

.knowledge-view {
  @apply grid h-dvh w-full min-h-0 min-w-0 overflow-hidden;

  grid-template-columns:
    minmax(0, 1fr)
    minmax(0, 1.92fr)
    minmax(0, 1fr);
  grid-template-areas: "files chat actions";
  grid-template-rows: minmax(0, 1fr);
  gap: 16px;
  width: 100%;
  box-sizing: border-box;
  padding: 16px;
  caret-color: transparent;
  color: var(--color-text);
  background: var(--color-surface-muted);
  font-size: 14px;
}

.knowledge-view.is-files-collapsed {
  grid-template-columns:
    56px
    minmax(0, 1.92fr)
    minmax(0, 1fr);
}

.knowledge-view.is-tools-collapsed {
  grid-template-columns:
    minmax(0, 1fr)
    minmax(0, 1.92fr)
    56px;
}

.knowledge-view.is-files-collapsed.is-tools-collapsed {
  grid-template-columns: 56px minmax(0, 1fr) 56px;
}

.knowledge-view-files {
  grid-area: files;
}

.knowledge-view-chat {
  grid-area: chat;
}

.knowledge-view-actions {
  grid-area: actions;
}

.knowledge-view :deep(input),
.knowledge-view :deep(textarea),
.knowledge-view :deep([contenteditable="true"]) {
  user-select: text;
  caret-color: auto;
}

@media (max-width: 720px) {
  .knowledge-view,
  .knowledge-view.is-files-collapsed,
  .knowledge-view.is-tools-collapsed,
  .knowledge-view.is-files-collapsed.is-tools-collapsed {
    overflow-y: auto;
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas:
      "chat"
      "files"
      "actions";
    grid-template-rows: none;
    grid-auto-rows: calc(100dvh - 32px);
  }
}
</style>
