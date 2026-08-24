<script setup lang="ts">
import type { Component } from "vue"
import {
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
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Settings,
  SquarePen,
  SquareTerminal
} from "@lucide/vue"
import { Dropdown as ADropdown, Menu as AMenu, MenuItem as AMenuItem, Tooltip as ATooltip } from "ant-design-vue"
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router"

import logoUrl from "@/assets/logo.svg"
import ProfileComponent from "@/components/ProfileComponent.vue"
import SearchChatComponent from "@/components/SearchChatComponent.vue"
import SettingsComponent from "@/components/SettingsComponent.vue"
import SidebarAccountComponent from "@/components/SidebarAccountComponent.vue"
import { useAuthStore } from "@/stores/useAuthStore"
import type { FeatureId } from "@/types/feature"

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const sidebarCollapsed = ref(false)
const mobileSidebarOpen = ref(false)
const profileOpen = ref(false)
const settingsOpen = ref(false)
const searchOpen = ref(false)
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

const isFeatureActive = (featureId: FeatureId | "knowledge") =>
  route.name === featureId

const updateViewport = (event?: MediaQueryListEvent) => {
  isNarrowViewport.value = event?.matches ?? viewportQuery?.matches ?? false
  if (!isNarrowViewport.value) mobileSidebarOpen.value = false
}

const onGlobalKeydown = (event: KeyboardEvent) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault()
    searchOpen.value = !searchOpen.value
  }
}

onMounted(() => {
  viewportQuery = window.matchMedia("(max-width: 900px)")
  updateViewport()
  viewportQuery.addEventListener("change", updateViewport)
  window.addEventListener("keydown", onGlobalKeydown)
})

onBeforeUnmount(() => {
  viewportQuery?.removeEventListener("change", updateViewport)
  window.removeEventListener("keydown", onGlobalKeydown)
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
  profileOpen.value = false
  settingsOpen.value = true
  mobileSidebarOpen.value = false
}

const openProfile = () => {
  settingsOpen.value = false
  profileOpen.value = true
  mobileSidebarOpen.value = false
}

const logout = async () => {
  profileOpen.value = false
  settingsOpen.value = false
  mobileSidebarOpen.value = false
  authStore.logout()
  await router.push({ name: "login" })
}
</script>

<template>
  <div class="flex h-dvh w-full overflow-hidden bg-paper text-graphite">
    <aside
      class="relative z-20 h-full shrink-0 overflow-hidden bg-mist transition-[width,flex-basis,transform] duration-200 ease-out max-[900px]:fixed max-[900px]:inset-y-0 max-[900px]:left-0 max-[900px]:z-50 max-[900px]:w-[min(86vw,19rem)] max-[900px]:basis-auto"
      :class="{
        'min-[900px]:w-[260px] min-[900px]:basis-[260px]':
          !isNarrowViewport && !sidebarCollapsed,
        'min-[900px]:w-[60px] min-[900px]:basis-[60px]':
          !isNarrowViewport && sidebarCollapsed,
        'max-[900px]:translate-x-0':
          isNarrowViewport && mobileSidebarOpen,
        'max-[900px]:-translate-x-[102%]':
          isNarrowViewport && !mobileSidebarOpen
      }"
      aria-label="Application navigation"
    >
      <div
        class="flex h-full flex-col overflow-hidden transition-[width] duration-200"
        :class="sidebarCollapsed && !isNarrowViewport
          ? 'w-[60px] min-w-[60px]'
          : 'w-[260px] min-w-[260px] max-[900px]:w-[min(86vw,19rem)] max-[900px]:min-w-[min(86vw,19rem)]'"
      >
        <!-- Expanded Sidebar Header -->
        <header
          v-if="!sidebarCollapsed || isNarrowViewport"
          class="flex min-h-[3.25rem] items-center justify-between px-4 pt-3 pb-1"
        >
          <RouterLink
            class="inline-flex min-w-0 items-center gap-2 font-semibold tracking-[-0.02em]"
            :to="{ name: 'chat' }"
            aria-label="AM home"
            @click="openNewConversation"
          >
            <img
              :src="logoUrl"
              class="h-[1.15rem] w-[1.15rem]"
              alt=""
            >
            <span class="truncate text-[0.95rem]">AM</span>
          </RouterLink>

          <div class="flex items-center gap-1">
            <ATooltip placement="right" title="Search (Cmd+K)">
              <button
                class="grid h-8 w-8 shrink-0 place-items-center rounded-sm bg-transparent text-slate transition-colors hover:bg-graphite/8 hover:text-graphite"
                type="button"
                aria-label="Search conversations"
                @click="searchOpen = true"
              >
                <Search
                  :size="18"
                  :stroke-width="1.8"
                  aria-hidden="true"
                />
              </button>
            </ATooltip>

            <ATooltip placement="right" title="Collapse sidebar">
              <button
                class="grid h-8 w-8 shrink-0 place-items-center rounded-sm bg-transparent text-slate transition-colors hover:bg-graphite/8 hover:text-graphite"
                type="button"
                aria-label="Collapse sidebar"
                @click="toggleSidebar"
              >
                <PanelLeftClose
                  :size="18"
                  :stroke-width="1.8"
                  aria-hidden="true"
                />
              </button>
            </ATooltip>
          </div>
        </header>

        <!-- Mini Collapsed Sidebar Header -->
        <header
          v-else
          class="flex min-h-[3.25rem] flex-col items-center justify-center gap-1 pt-3 pb-1"
        >
          <ATooltip placement="right" title="Expand sidebar">
            <button
              class="grid h-8 w-8 shrink-0 place-items-center rounded-sm bg-transparent text-slate transition-colors hover:bg-graphite/8 hover:text-graphite"
              type="button"
              aria-label="Expand sidebar"
              @click="toggleSidebar"
            >
              <PanelLeftOpen
                :size="18"
                :stroke-width="1.8"
                aria-hidden="true"
              />
            </button>
          </ATooltip>
        </header>

        <nav class="grid gap-2 px-1.5 pt-0.5 pb-2" aria-label="Primary navigation">
          <div class="grid gap-px">
            <ATooltip placement="right" :title="sidebarCollapsed && !isNarrowViewport ? 'New chat' : undefined">
              <button
                class="grid min-h-9 w-full items-center rounded-sm bg-transparent text-left text-sm hover:bg-graphite/8"
                :class="sidebarCollapsed && !isNarrowViewport ? 'flex justify-center px-0' : '[grid-template-columns:22px_minmax(0,1fr)] gap-2 px-2.5'"
                type="button"
                @click="openNewConversation"
              >
                <SquarePen
                  class="shrink-0"
                  :size="18"
                  :stroke-width="1.8"
                  aria-hidden="true"
                />
                <span v-if="!sidebarCollapsed || isNarrowViewport" class="truncate">New chat</span>
              </button>
            </ATooltip>
          </div>

          <div class="grid gap-px" aria-label="Features">
            <ATooltip
              v-for="featureLink in featureLinks"
              :key="featureLink.id"
              placement="right"
              :title="sidebarCollapsed && !isNarrowViewport ? featureLink.label : undefined"
            >
              <RouterLink
                class="grid min-h-9 w-full items-center rounded-sm bg-transparent text-sm hover:bg-graphite/8"
                :class="[
                  sidebarCollapsed && !isNarrowViewport ? 'flex justify-center px-0' : '[grid-template-columns:22px_minmax(0,1fr)] gap-2 px-2.5',
                  { 'bg-graphite/8 font-semibold': isFeatureActive(featureLink.id) }
                ]"
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
                <span v-if="!sidebarCollapsed || isNarrowViewport" class="truncate">
                  {{ featureLink.label }}
                </span>
              </RouterLink>
            </ATooltip>
          </div>
        </nav>

        <div class="min-h-0 flex-1" />

        <footer class="grid gap-px px-1.5 pt-1 pb-3">
          <ATooltip v-if="sidebarCollapsed && !isNarrowViewport" placement="right" title="Search (Cmd+K)">
            <button
              class="flex min-h-9 items-center justify-center rounded-sm bg-transparent text-slate hover:bg-graphite/8 hover:text-graphite mb-1 w-full"
              type="button"
              aria-label="Search conversations"
              @click="searchOpen = true"
            >
              <Search
                :size="18"
                :stroke-width="1.8"
                aria-hidden="true"
              />
            </button>
          </ATooltip>

          <ATooltip v-if="!authStore.accessToken" placement="right" :title="sidebarCollapsed && !isNarrowViewport ? 'Log in' : undefined">
            <RouterLink
              class="flex min-h-9 items-center rounded-sm bg-transparent text-left text-sm text-slate hover:bg-graphite/8 hover:text-graphite"
              :class="sidebarCollapsed && !isNarrowViewport ? 'justify-center px-0' : 'gap-2 px-2.5'"
              to="/login"
            >
              <LogIn
                :size="17"
                :stroke-width="1.8"
                aria-hidden="true"
              />
              <span v-if="!sidebarCollapsed || isNarrowViewport">Log in</span>
            </RouterLink>
          </ATooltip>

          <SidebarAccountComponent
            v-if="authStore.accessToken"
            username="AM User"
            :collapsed="sidebarCollapsed && !isNarrowViewport"
            @profile="openProfile"
            @settings="openSettings"
            @logout="logout"
          />
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
      <header class="group flex min-h-[52px] shrink-0 items-center justify-end gap-4 px-[clamp(0.75rem,2vw,1.25rem)] py-2">
        <nav
          class="flex items-center gap-1"
          aria-label="Secondary actions"
        >
          <ATooltip placement="bottom" title="More options">
            <ADropdown placement="bottomRight" trigger="click">
              <button
                class="grid h-9 w-9 place-items-center rounded-sm bg-transparent text-slate hover:bg-mist hover:text-graphite"
                type="button"
                aria-label="More options"
              >
                <MoreHorizontal
                  :size="18"
                  :stroke-width="1.8"
                  aria-hidden="true"
                />
              </button>
              <template #overlay>
                <AMenu>
                  <AMenuItem key="new-chat" @click="openNewConversation">
                    <div class="flex items-center gap-2 text-xs">
                      <SquarePen :size="14" />
                      <span>New chat</span>
                    </div>
                  </AMenuItem>
                  <AMenuItem key="settings" @click="openSettings">
                    <div class="flex items-center gap-2 text-xs">
                      <Settings :size="14" />
                      <span>Settings</span>
                    </div>
                  </AMenuItem>
                </AMenu>
              </template>
            </ADropdown>
          </ATooltip>
          <RouterLink
            v-if="!authStore.accessToken"
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

  <ProfileComponent
    :open="profileOpen"
    :user="authStore.user"
    username="AM User"
    @close="profileOpen = false"
  />

  <SettingsComponent
    :open="settingsOpen"
    :user="authStore.user"
    @close="settingsOpen = false"
  />

  <SearchChatComponent
    :open="searchOpen"
    @close="searchOpen = false"
  />
</template>
