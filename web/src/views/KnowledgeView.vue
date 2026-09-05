<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from "vue"
import { gsap } from "gsap"
import {
  BookOpenCheck,
  Bot,
  Layers,
  Library,
  LogIn,
  SquarePen,
  SquareTerminal
} from "@lucide/vue"
import { RouterLink } from "vue-router"

import logoUrl from "@/assets/logo.svg"
import KnowledgeChatComponent from "@/components/knowledge/KnowledgeChatComponent.vue"
import KnowledgeFileActionsComponent from "@/components/knowledge/KnowledgeFileActionsComponent.vue"
import KnowledgeFilesComponent from "@/components/knowledge/KnowledgeFilesComponent.vue"
import type { KnowledgeFileItem } from "@/types/knowledge"

const files = ref<KnowledgeFileItem[]>([])
const selectedFileId = ref<string | null>(null)
const filesCollapsed = ref(false)
const toolsCollapsed = ref(false)
const knowledgeView = ref<HTMLElement | null>(null)

const isRailHovered = ref(false)
let railHoverTimer: ReturnType<typeof setTimeout> | null = null

const onRailMouseEnter = () => {
  if (railHoverTimer) {
    clearTimeout(railHoverTimer)
    railHoverTimer = null
  }
  isRailHovered.value = true
}

const onRailMouseLeave = () => {
  railHoverTimer = setTimeout(() => {
    isRailHovered.value = false
    railHoverTimer = null
  }, 100)
}

const navLinks = [
  { id: "chat", label: "Chat", icon: SquarePen, to: "/" },
  { id: "library", label: "Library", icon: Library, to: "/library" },
  { id: "knowledge", label: "Knowledge", icon: BookOpenCheck, to: "/knowledge" },
  { id: "agent", label: "Agent", icon: Bot, to: "/agent" },
  { id: "static", label: "Static", icon: Layers, to: "/static" },
  { id: "sandbox", label: "Sandbox", icon: SquareTerminal, to: "/sandbox" }
]

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
  if (railHoverTimer) clearTimeout(railHoverTimer)
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
  <div class="flex h-dvh w-full overflow-hidden bg-mist p-2.5 gap-2.5 text-graphite relative font-sans">
    <!-- Left Navigation Rail (Seamless, expands on hover without container lines) -->
    <div
      class="relative h-full shrink-0 select-none z-30 w-[56px]"
      @mouseenter="onRailMouseEnter"
      @mouseleave="onRailMouseLeave"
    >
      <aside
        class="flex h-full flex-col overflow-hidden bg-mist py-2 text-slate border-0 shadow-none outline-none transition-[width] duration-250 ease-[cubic-bezier(0.16,1,0.3,1)]"
        :class="[
          isRailHovered
            ? 'absolute inset-y-0 left-0 z-40 w-[220px] px-1.5'
            : 'w-[56px] items-center px-1'
        ]"
        aria-label="Application navigation"
      >
        <!-- Rail Header: Brand / Home Link -->
        <header class="flex h-11 shrink-0 items-center gap-3 px-1.5 mb-2">
          <RouterLink
            class="flex items-center gap-3 font-semibold text-graphite tracking-[-0.02em] hover:text-graphite"
            to="/"
            aria-label="AM home"
          >
            <span class="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-graphite text-paper font-bold text-xs shadow-sm">
              <img
                :src="logoUrl"
                class="h-4.5 w-4.5 invert"
                alt=""
              >
            </span>
            <span
              class="truncate text-sm font-semibold text-graphite transition-opacity duration-150"
              :class="isRailHovered ? 'opacity-100' : 'opacity-0 pointer-events-none w-0'"
            >
              AM
            </span>
          </RouterLink>
        </header>

        <!-- Primary Navigation -->
        <nav class="grid gap-1.5 pt-1 pb-2 w-full" aria-label="Primary navigation">
          <RouterLink
            v-for="item in navLinks"
            :key="item.id"
            class="grid h-10 w-full items-center rounded-xl text-left text-sm transition-colors"
            :class="[
              isRailHovered
                ? '[grid-template-columns:36px_minmax(0,1fr)] gap-1 px-1'
                : 'grid-cols-1 place-items-center px-0',
              item.id === 'knowledge'
                ? 'bg-graphite/10 text-graphite font-semibold'
                : 'text-slate hover:bg-graphite/6 hover:text-graphite'
            ]"
            :to="item.to"
            :title="item.label"
          >
            <span class="grid h-8 w-8 place-items-center">
              <component
                :is="item.icon"
                :size="18"
                :stroke-width="item.id === 'knowledge' ? 2 : 1.8"
                aria-hidden="true"
              />
            </span>
            <span
              class="truncate transition-opacity duration-150"
              :class="isRailHovered ? 'opacity-100' : 'opacity-0 pointer-events-none w-0'"
            >
              {{ item.label }}
            </span>
          </RouterLink>
        </nav>

        <div class="min-h-0 flex-1" />

        <!-- Bottom Return to Home -->
        <footer class="grid gap-1 pt-2 pb-1 w-full">
          <RouterLink
            class="grid h-10 w-full items-center rounded-xl text-left text-sm text-slate transition-colors hover:bg-graphite/6 hover:text-graphite"
            :class="[
              isRailHovered
                ? '[grid-template-columns:36px_minmax(0,1fr)] gap-1 px-1'
                : 'grid-cols-1 place-items-center px-0'
            ]"
            to="/"
            title="Back to Home"
          >
            <span class="grid h-8 w-8 place-items-center">
              <LogIn
                :size="18"
                :stroke-width="1.8"
                aria-hidden="true"
              />
            </span>
            <span
              class="truncate transition-opacity duration-150"
              :class="isRailHovered ? 'opacity-100' : 'opacity-0 pointer-events-none w-0'"
            >
              Back to Home
            </span>
          </RouterLink>
        </footer>
      </aside>
    </div>

    <!-- Right Large Rounded-Rectangle App Shell Container -->
    <div class="relative flex min-w-0 flex-1 flex-col overflow-hidden rounded-[20px] bg-paper border border-graphite/10 shadow-sm text-graphite">
      <!-- Header bar inside the shell -->
      <header class="flex min-h-[46px] shrink-0 items-center justify-between border-b border-graphite/6 px-4 py-1.5 bg-paper">
        <div class="flex items-center gap-2">
          <span class="font-medium text-xs tracking-wider uppercase text-slate/80 select-none">
            Knowledge Base
          </span>
        </div>
      </header>

      <!-- Knowledge Workspace (3 Panels) -->
      <main
        ref="knowledgeView"
        class="grid h-full w-full min-h-0 min-w-0 overflow-hidden gap-3 bg-mist p-3 text-sm text-graphite [grid-template-rows:minmax(0,1fr)] [grid-template-areas:'files_chat_actions'] max-[720px]:overflow-y-auto max-[720px]:grid-cols-[minmax(0,1fr)] max-[720px]:[grid-template-areas:'chat'_'files'_'actions'] max-[720px]:grid-rows-none max-[720px]:[grid-auto-rows:calc(100dvh_-_32px)]"
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
    </div>
  </div>
</template>
