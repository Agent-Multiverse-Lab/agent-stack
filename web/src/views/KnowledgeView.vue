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

/** 生成只用于当前页面状态的文件标识。 */
function createFileId(): string {
  return crypto.randomUUID()
}

/** 将浏览器文件选择结果转换为知识页文件记录。 */
function createKnowledgeFile(file: File): KnowledgeFileItem {
  const extension = file.name.split(".").pop()?.toUpperCase() || "FILE"

  return {
    id: createFileId(),
    source: file,
    name: file.name,
    size: file.size,
    mimeType: file.type,
    extension,
    lastModified: file.lastModified,
    status: "selected"
  }
}

/** 合并新选择的文件，并保持当前选择稳定。 */
function addFiles(selectedFiles: File[]) {
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

/** 从文件集合移除一项，并选择最接近的剩余文件。 */
function removeFile(fileId: string) {
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
    class="grid h-dvh w-full min-h-0 min-w-0 overflow-hidden gap-4 bg-mist p-4 text-sm text-graphite [grid-template-rows:minmax(0,1fr)] [grid-template-areas:'files_chat_actions'] max-[720px]:overflow-y-auto max-[720px]:grid-cols-[minmax(0,1fr)] max-[720px]:[grid-template-areas:'chat'_'files'_'actions'] max-[720px]:grid-rows-none max-[720px]:[grid-auto-rows:calc(100dvh_-_32px)]"
    :class="{
      '[grid-template-columns:minmax(0,1fr)_minmax(0,1.92fr)_minmax(0,1fr)]':
        !filesCollapsed && !toolsCollapsed,
      '[grid-template-columns:56px_minmax(0,1.92fr)_minmax(0,1fr)]':
        filesCollapsed && !toolsCollapsed,
      '[grid-template-columns:minmax(0,1fr)_minmax(0,1.92fr)_56px]':
        !filesCollapsed && toolsCollapsed,
      '[grid-template-columns:56px_minmax(0,1fr)_56px]':
        filesCollapsed && toolsCollapsed
    }"
  >
    <KnowledgeFilesComponent
      class="[grid-area:files]"
      :files="files"
      :selected-file-id="selectedFileId"
      :collapsed="filesCollapsed"
      presentation="panel"
      :open="false"
      @files-selected="addFiles"
      @select="selectedFileId = $event"
      @remove="removeFile"
      @toggle-collapse="toggleFilesCollapsed"
    />

    <KnowledgeChatComponent
      class="[grid-area:chat]"
      :files="files"
    />

    <KnowledgeFileActionsComponent
      class="[grid-area:actions]"
      :collapsed="toolsCollapsed"
      presentation="panel"
      :open="false"
      @toggle-collapse="toggleToolsCollapsed"
    />
  </main>
</template>
