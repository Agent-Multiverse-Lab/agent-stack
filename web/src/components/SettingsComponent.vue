<script setup lang="ts">
import type { Component } from "vue"
import { computed, onBeforeUnmount, ref, watch } from "vue"
import { Database, Info, Settings, User, X } from "@lucide/vue"
import { RouterLink } from "vue-router"

import type { UserResponse } from "@/types/auth"

type SettingsSectionId = "general" | "account" | "data" | "about"

interface SettingsSection {
  id: SettingsSectionId
  label: string
  icon: Component
}

const props = defineProps<{
  open: boolean
  user: UserResponse | null
}>()

const emit = defineEmits<{
  close: []
}>()

const sections: SettingsSection[] = [
  { id: "general", label: "General", icon: Settings },
  { id: "account", label: "Account", icon: User },
  { id: "data", label: "Data Controls", icon: Database },
  { id: "about", label: "About", icon: Info }
]

const activeSection = ref<SettingsSectionId>("general")
const theme = ref("light")
const language = ref("en")
const showFollowUps = ref(true)
const improveModel = ref(false)

const accountStatus = computed(() => {
  if (!props.user) return "Not logged in"
  return props.user.is_active ? "Active" : "Inactive"
})

const close = () => emit("close")

const onKeydown = (event: KeyboardEvent) => {
  if (event.key === "Escape") close()
}

watch(
  () => props.open,
  (open) => {
    document.body.toggleAttribute("data-modal-open", open)

    if (open) {
      activeSection.value = "general"
      document.addEventListener("keydown", onKeydown)
      return
    }

    document.removeEventListener("keydown", onKeydown)
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  document.body.removeAttribute("data-modal-open")
  document.removeEventListener("keydown", onKeydown)
})
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-150 ease-out motion-reduce:transition-none"
      leave-active-class="transition-opacity duration-150 ease-in motion-reduce:transition-none"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        class="fixed inset-0 z-[100] grid place-items-end bg-graphite/36 min-[768px]:place-items-center min-[768px]:p-6"
        @mousedown.self="close"
      >
        <section
          class="flex h-[min(92dvh,760px)] w-full flex-col overflow-hidden rounded-t-lg bg-paper text-graphite min-[768px]:h-[min(640px,calc(100dvh_-_48px))] min-[768px]:max-w-[860px] min-[768px]:rounded-lg"
          role="dialog"
          aria-modal="true"
          aria-labelledby="settings-title"
        >
          <header class="flex min-h-[3.25rem] shrink-0 items-center justify-between gap-4 pt-1 pr-3 pb-1 pl-5">
            <h2 id="settings-title" class="m-0 font-semibold text-[0.95rem] tracking-[-0.02em]">
              Settings
            </h2>

            <button
              class="inline-flex h-9 w-9 items-center justify-center rounded-sm bg-transparent text-slate transition-colors duration-150 hover:bg-mist hover:text-graphite motion-reduce:transition-none"
              type="button"
              aria-label="Close settings"
              @click="close"
            >
              <X
                class="shrink-0"
                :size="19"
                :stroke-width="1.8"
                aria-hidden="true"
              />
            </button>
          </header>

          <div class="grid min-h-0 flex-1 [grid-template-rows:auto_minmax(0,1fr)] min-[768px]:grid-rows-1 min-[768px]:[grid-template-columns:minmax(150px,2fr)_minmax(0,8fr)]">
            <nav
              class="flex min-w-0 gap-0.5 overflow-x-auto border-b border-graphite/6 px-3 py-2 min-[768px]:h-full min-[768px]:flex-col min-[768px]:overflow-y-auto min-[768px]:border-b-0 min-[768px]:border-r min-[768px]:border-graphite/6"
              aria-label="Settings sections"
              role="tablist"
            >
              <button
                v-for="section in sections"
                :id="`settings-tab-${section.id}`"
                :key="section.id"
                class="flex min-h-8 shrink-0 items-center gap-2 rounded-sm bg-transparent px-2.5 text-left text-[0.88rem] font-normal text-slate transition-colors duration-150 hover:bg-mist hover:text-graphite motion-reduce:transition-none min-[768px]:w-full min-[768px]:min-h-9"
                :class="{ 'font-semibold text-graphite': activeSection === section.id }"
                type="button"
                role="tab"
                :aria-controls="`settings-section-${section.id}`"
                :aria-selected="activeSection === section.id"
                @click="activeSection = section.id"
              >
                <component
                  :is="section.icon"
                  class="h-[1.1rem] w-[1.1rem] shrink-0"
                  :size="18"
                  :stroke-width="activeSection === section.id ? 2 : 1.7"
                  aria-hidden="true"
                />
                <span class="whitespace-nowrap">{{ section.label }}</span>
              </button>
            </nav>

            <div
              class="h-full min-h-0 min-w-0 overflow-y-auto bg-paper px-4 pt-4 pb-6 min-[768px]:px-7 min-[768px]:pt-5 min-[768px]:pb-7"
              aria-live="polite"
            >
              <section
                v-if="activeSection === 'general'"
                id="settings-section-general"
                class="grid min-w-0 gap-5"
                role="tabpanel"
                aria-labelledby="settings-tab-general"
              >
                <h3 class="m-0 text-base font-semibold tracking-[-0.02em]">General</h3>

                <div class="grid min-w-0">
                  <div class="flex min-h-12 items-center justify-between gap-5 border-b border-graphite/6 py-3 text-sm">
                    <label class="min-w-0" for="settings-theme">Theme</label>
                    <select
                      id="settings-theme"
                      v-model="theme"
                      class="h-8 min-w-28 max-w-[55%] bg-transparent text-right text-sm text-slate hover:text-graphite focus:text-graphite"
                    >
                      <option class="text-graphite" value="light">Light</option>
                      <option class="text-graphite" value="system">System</option>
                      <option class="text-graphite" value="dark">Dark</option>
                    </select>
                  </div>

                  <div class="flex min-h-12 items-center justify-between gap-5 border-b border-graphite/6 py-3 text-sm">
                    <label class="min-w-0" for="settings-language">Language</label>
                    <select
                      id="settings-language"
                      v-model="language"
                      class="h-8 min-w-28 max-w-[55%] bg-transparent text-right text-sm text-slate hover:text-graphite focus:text-graphite"
                    >
                      <option class="text-graphite" value="en">English</option>
                      <option class="text-graphite" value="zh-CN">简体中文</option>
                    </select>
                  </div>

                  <div class="flex min-h-12 items-center justify-between gap-5 border-b border-graphite/6 py-3 text-sm">
                    <span class="min-w-0">Show follow-up suggestions</span>
                    <button
                      class="relative h-6 w-10 shrink-0 rounded-full bg-graphite/6 transition-colors duration-140 motion-reduce:transition-none"
                      :class="{ 'bg-graphite': showFollowUps }"
                      type="button"
                      role="switch"
                      :aria-checked="showFollowUps"
                      aria-label="Show follow-up suggestions"
                      @click="showFollowUps = !showFollowUps"
                    >
                      <span
                        class="absolute left-[3px] top-[3px] h-[18px] w-[18px] rounded-full bg-paper transition-transform duration-140 motion-reduce:transition-none"
                        :class="{ 'translate-x-4': showFollowUps }"
                        aria-hidden="true"
                      />
                    </button>
                  </div>
                </div>
              </section>

              <section
                v-else-if="activeSection === 'account'"
                id="settings-section-account"
                class="grid min-w-0 gap-5"
                role="tabpanel"
                aria-labelledby="settings-tab-account"
              >
                <h3 class="m-0 text-base font-semibold tracking-[-0.02em]">Account</h3>

                <div class="grid min-w-0">
                  <div class="flex min-h-12 items-center justify-between gap-5 border-b border-graphite/6 py-3 text-sm">
                    <span class="min-w-0">Status</span>
                    <span class="text-right text-slate">{{ accountStatus }}</span>
                  </div>

                  <div class="flex min-h-12 items-center justify-between gap-5 border-b border-graphite/6 py-3 text-sm">
                    <span class="min-w-0">Account</span>
                    <span v-if="user" class="min-w-0 truncate text-right text-slate">
                      {{ user.email }}
                    </span>
                    <RouterLink
                      v-else
                      class="font-medium underline underline-offset-2"
                      to="/login"
                      @click="close"
                    >
                      Log in
                    </RouterLink>
                  </div>
                </div>
              </section>

              <section
                v-else-if="activeSection === 'data'"
                id="settings-section-data"
                class="grid min-w-0 gap-5"
                role="tabpanel"
                aria-labelledby="settings-tab-data"
              >
                <h3 class="m-0 text-base font-semibold tracking-[-0.02em]">Data Controls</h3>

                <div class="grid min-w-0">
                  <div class="flex min-h-12 items-center justify-between gap-5 border-b border-graphite/6 py-3 text-sm">
                    <span class="min-w-0">Improve the model</span>
                    <button
                      class="relative h-6 w-10 shrink-0 rounded-full bg-graphite/6 transition-colors duration-140 motion-reduce:transition-none"
                      :class="{ 'bg-graphite': improveModel }"
                      type="button"
                      role="switch"
                      :aria-checked="improveModel"
                      aria-label="Improve the model"
                      @click="improveModel = !improveModel"
                    >
                      <span
                        class="absolute left-[3px] top-[3px] h-[18px] w-[18px] rounded-full bg-paper transition-transform duration-140 motion-reduce:transition-none"
                        :class="{ 'translate-x-4': improveModel }"
                        aria-hidden="true"
                      />
                    </button>
                  </div>
                </div>
              </section>

              <section
                v-else
                id="settings-section-about"
                class="grid min-w-0 gap-5"
                role="tabpanel"
                aria-labelledby="settings-tab-about"
              >
                <h3 class="m-0 text-base font-semibold tracking-[-0.02em]">About</h3>

                <div class="grid min-w-0">
                  <div class="flex min-h-12 items-center justify-between gap-5 border-b border-graphite/6 py-3 text-sm">
                    <span class="min-w-0">Product</span>
                    <span class="text-right text-slate">AM</span>
                  </div>

                  <div class="flex min-h-12 items-center justify-between gap-5 border-b border-graphite/6 py-3 text-sm">
                    <span class="min-w-0">Version</span>
                    <span class="text-right text-slate">Preview</span>
                  </div>
                </div>
              </section>
            </div>
          </div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>
