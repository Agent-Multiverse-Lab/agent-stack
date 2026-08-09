<script setup lang="ts">
import type { Component } from "vue"
import {
  computed,
  onBeforeUnmount,
  onMounted,
  ref,
  watch
} from "vue"
import {
  BookOpenCheck,
  Bot,
  Layers,
  Library,
  LogIn,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  SquarePen,
  SquareTerminal
} from "@lucide/vue"
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router"

import logoUrl from "@/assets/logo.svg"
import SettingsComponent from "@/components/SettingsComponent.vue"
import type { FeatureId } from "@/types/feature"

const route = useRoute()
const router = useRouter()

const sidebarCollapsed = ref(false)
const mobileSidebarOpen = ref(false)
const settingsOpen = ref(false)
const isNarrowViewport = ref(false)

let viewportQuery: MediaQueryList | null = null

const featureLinks: Array<{
  id: FeatureId | "knowledge"
  label: string
  icon: Component
}> = [
  { id: "library", label: "Library", icon: Library },
  { id: "knowledge", label: "Knowledge", icon: BookOpenCheck },
  { id: "agent", label: "Agent", icon: Bot },
  { id: "static", label: "Static", icon: Layers },
  { id: "sandbox", label: "Sandbox", icon: SquareTerminal }
]

const pageTitle = computed(() =>
  typeof route.meta.title === "string" ? route.meta.title : "Chat"
)
const isChatRoute = computed(
  () => route.name === "chat" || route.name === "conversation"
)
const sidebarVisible = computed(() =>
  isNarrowViewport.value
    ? mobileSidebarOpen.value
    : !sidebarCollapsed.value
)
const isFeatureActive = (featureId: FeatureId | "knowledge") =>
  route.name === featureId

const updateViewport = (event?: MediaQueryListEvent) => {
  isNarrowViewport.value = event?.matches ?? viewportQuery?.matches ?? false
  if (!isNarrowViewport.value) mobileSidebarOpen.value = false
}

onMounted(() => {
  viewportQuery = window.matchMedia("(max-width: 900px)")
  updateViewport()
  viewportQuery.addEventListener("change", updateViewport)
})

onBeforeUnmount(() => {
  viewportQuery?.removeEventListener("change", updateViewport)
})

watch(
  () => route.fullPath,
  () => {
    mobileSidebarOpen.value = false
  }
)

const toggleSidebar = () => {
  if (isNarrowViewport.value) {
    mobileSidebarOpen.value = !mobileSidebarOpen.value
    return
  }

  sidebarCollapsed.value = !sidebarCollapsed.value
}

const openNewConversation = async () => {
  mobileSidebarOpen.value = false

  if (route.name !== "chat") {
    await router.push({ name: "chat" })
  }
}

const openSettings = () => {
  settingsOpen.value = true
}
</script>

<template>
  <div class="flex h-dvh w-full overflow-hidden bg-paper text-graphite">
    <aside
      class="relative z-20 h-full shrink-0 overflow-hidden bg-mist transition-[width,flex-basis,transform] duration-200 ease-out max-[900px]:fixed max-[900px]:inset-y-0 max-[900px]:left-0 max-[900px]:z-50 max-[900px]:w-[min(86vw,19rem)] max-[900px]:basis-auto"
      :class="{
        'min-[900px]:w-[260px] min-[900px]:basis-[260px]':
          !isNarrowViewport && !sidebarCollapsed,
        'min-[900px]:w-0 min-[900px]:basis-0':
          !isNarrowViewport && sidebarCollapsed,
        'max-[900px]:translate-x-0':
          isNarrowViewport && mobileSidebarOpen,
        'max-[900px]:-translate-x-[102%]':
          isNarrowViewport && !mobileSidebarOpen
      }"
      aria-label="Application navigation"
    >
      <div
        class="flex h-full w-[260px] min-w-[260px] flex-col overflow-hidden max-[900px]:w-[min(86vw,19rem)] max-[900px]:min-w-[min(86vw,19rem)]"
      >
        <header class="flex min-h-[3.25rem] items-center justify-between px-4 pt-3 pb-1">
          <RouterLink
            class="inline-flex min-w-0 items-center gap-2 font-semibold tracking-[-0.02em]"
            :to="{ name: 'chat' }"
            aria-label="AU home"
            @click="openNewConversation"
          >
            <img
              :src="logoUrl"
              class="h-[1.15rem] w-[1.15rem]"
              alt=""
            >
            <span class="truncate text-[0.95rem]">AU</span>
          </RouterLink>

          <button
            v-if="isNarrowViewport"
            class="grid h-8 w-8 shrink-0 place-items-center rounded-sm bg-transparent text-slate hover:bg-graphite/8 hover:text-graphite"
            type="button"
            aria-label="Close sidebar"
            @click="mobileSidebarOpen = false"
          >
            <PanelLeftClose
              :size="18"
              :stroke-width="1.8"
              aria-hidden="true"
            />
          </button>
        </header>

        <nav class="grid gap-2 px-1.5 pt-0.5 pb-2" aria-label="Primary navigation">
          <div class="grid gap-px">
            <button
              class="grid min-h-9 w-full items-center gap-2 rounded-sm bg-transparent px-2.5 text-left text-sm [grid-template-columns:22px_minmax(0,1fr)] hover:bg-graphite/8"
              type="button"
              @click="openNewConversation"
            >
              <SquarePen
                class="shrink-0"
                :size="18"
                :stroke-width="1.8"
                aria-hidden="true"
              />
              <span class="truncate">New chat</span>
            </button>
          </div>

          <div class="grid gap-px" aria-label="Features">
            <RouterLink
              v-for="featureLink in featureLinks"
              :key="featureLink.id"
              class="grid min-h-9 w-full items-center gap-2 rounded-sm bg-transparent px-2.5 text-sm [grid-template-columns:22px_minmax(0,1fr)] hover:bg-graphite/8"
              :class="{
                'bg-graphite/8 font-semibold': isFeatureActive(featureLink.id)
              }"
              :to="{ name: featureLink.id }"
              @click="mobileSidebarOpen = false"
            >
              <component
                :is="featureLink.icon"
                class="shrink-0"
                :size="18"
                :stroke-width="isFeatureActive(featureLink.id) ? 2 : 1.8"
                aria-hidden="true"
              />
              <span class="truncate">
                {{ featureLink.label }}
              </span>
            </RouterLink>
          </div>
        </nav>

        <div class="min-h-0 flex-1" />

        <footer class="grid gap-px px-1.5 pt-1 pb-3">
          <RouterLink
            class="flex min-h-9 items-center gap-2 rounded-sm bg-transparent px-2.5 text-left text-sm text-slate hover:bg-graphite/8 hover:text-graphite"
            to="/login"
          >
            <LogIn
              :size="17"
              :stroke-width="1.8"
              aria-hidden="true"
            />
            <span>Log in</span>
          </RouterLink>
          <button
            class="flex min-h-9 items-center gap-2 rounded-sm bg-transparent px-2.5 text-left text-sm text-slate hover:bg-graphite/8 hover:text-graphite"
            type="button"
            @click="openSettings"
          >
            <Settings
              :size="17"
              :stroke-width="1.8"
              aria-hidden="true"
            />
            <span>Settings</span>
          </button>
        </footer>
      </div>
    </aside>

    <button
      v-if="isNarrowViewport && mobileSidebarOpen"
      class="fixed inset-0 z-40 bg-graphite/36"
      type="button"
      aria-label="Close sidebar"
      @click="mobileSidebarOpen = false"
    />

    <main class="flex min-w-0 flex-1 flex-col overflow-hidden">
      <header class="group flex min-h-[52px] shrink-0 items-center justify-between gap-4 px-[clamp(0.75rem,2vw,1.25rem)] py-2">
        <div class="flex min-w-0 items-center gap-1.5">
          <button
            class="grid h-9 w-9 shrink-0 place-items-center rounded-sm bg-transparent text-slate hover:bg-mist hover:text-graphite"
            type="button"
            :aria-label="sidebarVisible ? 'Collapse sidebar' : 'Expand sidebar'"
            :title="sidebarVisible ? 'Collapse sidebar' : 'Expand sidebar'"
            @click="toggleSidebar"
          >
            <PanelLeftClose
              v-if="sidebarVisible"
              :size="19"
              :stroke-width="1.8"
              aria-hidden="true"
            />
            <PanelLeftOpen
              v-else
              :size="19"
              :stroke-width="1.8"
              aria-hidden="true"
            />
          </button>
          <h1 class="m-0 truncate text-base font-semibold tracking-[-0.02em]">
            {{ pageTitle }}
          </h1>
        </div>

        <nav
          class="flex min-w-0 items-center gap-1.5"
          aria-label="Account actions"
        >
          <button
            v-if="isChatRoute"
            class="grid h-9 w-9 shrink-0 place-items-center rounded-sm bg-transparent text-slate opacity-0 transition-colors duration-100 group-hover:opacity-100 group-focus-within:opacity-100 hover:bg-mist hover:text-graphite pointer-coarse:opacity-100"
            type="button"
            aria-label="New chat"
            title="New chat"
            @click="openNewConversation"
          >
            <SquarePen
              :size="17"
              :stroke-width="1.8"
              aria-hidden="true"
            />
          </button>
          <RouterLink
            class="inline-flex min-h-[34px] items-center rounded-sm px-3 text-[13px] font-medium text-slate hover:bg-mist hover:text-graphite"
            to="/login"
          >
            Log in
          </RouterLink>
        </nav>
      </header>

      <div class="min-h-0 flex-1 overflow-hidden">
        <RouterView />
      </div>
    </main>
  </div>

  <SettingsComponent
    :open="settingsOpen"
    @close="settingsOpen = false"
  />
</template>
