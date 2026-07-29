<script setup lang="ts">
import type { Component } from "vue"
import { onBeforeUnmount, ref, watch } from "vue"
import { Database, Info, Settings, User, X } from "@lucide/vue"
import { RouterLink } from "vue-router"

type SettingsSectionId = "general" | "account" | "data" | "about"

interface SettingsSection {
  id: SettingsSectionId
  label: string
  icon: Component
}

const props = defineProps<{
  open: boolean
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
const saveLocalHistory = ref(true)
const improveModel = ref(false)

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
    <Transition name="settings-modal-transition">
      <div
        v-if="open"
        class="settings-modal-layer"
        @mousedown.self="close"
      >
        <section
          class="settings-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="settings-title"
        >
          <header class="settings-modal-header">
            <h2 id="settings-title" class="settings-modal-title">
              Settings
            </h2>

            <button
              class="settings-close-button"
              type="button"
              aria-label="Close settings"
              @click="close"
            >
              <X
                class="settings-close-icon"
                :size="19"
                :stroke-width="1.8"
                aria-hidden="true"
              />
            </button>
          </header>

          <div class="settings-layout">
            <nav
              class="settings-navigation"
              aria-label="Settings sections"
              role="tablist"
            >
              <button
                v-for="section in sections"
                :id="`settings-tab-${section.id}`"
                :key="section.id"
                class="settings-navigation-button"
                :class="{ 'is-active': activeSection === section.id }"
                type="button"
                role="tab"
                :aria-controls="`settings-section-${section.id}`"
                :aria-selected="activeSection === section.id"
                @click="activeSection = section.id"
              >
                <component
                  :is="section.icon"
                  class="settings-navigation-icon"
                  :size="18"
                  :stroke-width="activeSection === section.id ? 2 : 1.7"
                  aria-hidden="true"
                />
                <span class="settings-navigation-label">{{ section.label }}</span>
              </button>
            </nav>

            <div
              class="settings-content"
              aria-live="polite"
            >
              <section
                v-if="activeSection === 'general'"
                id="settings-section-general"
                class="settings-section"
                role="tabpanel"
                aria-labelledby="settings-tab-general"
              >
                <h3 class="settings-section-title">General</h3>

                <div class="settings-list">
                  <div class="settings-row">
                    <label class="settings-row-label" for="settings-theme">Theme</label>
                    <select
                      id="settings-theme"
                      v-model="theme"
                      class="settings-select"
                    >
                      <option class="settings-select-option" value="light">Light</option>
                      <option class="settings-select-option" value="system">System</option>
                      <option class="settings-select-option" value="dark">Dark</option>
                    </select>
                  </div>

                  <div class="settings-row">
                    <label class="settings-row-label" for="settings-language">Language</label>
                    <select
                      id="settings-language"
                      v-model="language"
                      class="settings-select"
                    >
                      <option class="settings-select-option" value="en">English</option>
                      <option class="settings-select-option" value="zh-CN">简体中文</option>
                    </select>
                  </div>

                  <div class="settings-row">
                    <span class="settings-row-label">Show follow-up suggestions</span>
                    <button
                      class="settings-switch"
                      :class="{ 'is-on': showFollowUps }"
                      type="button"
                      role="switch"
                      :aria-checked="showFollowUps"
                      aria-label="Show follow-up suggestions"
                      @click="showFollowUps = !showFollowUps"
                    >
                      <span
                        class="settings-switch-thumb"
                        aria-hidden="true"
                      />
                    </button>
                  </div>
                </div>
              </section>

              <section
                v-else-if="activeSection === 'account'"
                id="settings-section-account"
                class="settings-section"
                role="tabpanel"
                aria-labelledby="settings-tab-account"
              >
                <h3 class="settings-section-title">Account</h3>

                <div class="settings-list">
                  <div class="settings-row">
                    <span class="settings-row-label">Status</span>
                    <span class="settings-value">Not logged in</span>
                  </div>

                  <div class="settings-row">
                    <span class="settings-row-label">Account</span>
                    <RouterLink
                      class="settings-login-link"
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
                class="settings-section"
                role="tabpanel"
                aria-labelledby="settings-tab-data"
              >
                <h3 class="settings-section-title">Data Controls</h3>

                <div class="settings-list">
                  <div class="settings-row">
                    <span class="settings-row-label">Save local chat history</span>
                    <button
                      class="settings-switch"
                      :class="{ 'is-on': saveLocalHistory }"
                      type="button"
                      role="switch"
                      :aria-checked="saveLocalHistory"
                      aria-label="Save local chat history"
                      @click="saveLocalHistory = !saveLocalHistory"
                    >
                      <span
                        class="settings-switch-thumb"
                        aria-hidden="true"
                      />
                    </button>
                  </div>

                  <div class="settings-row">
                    <span class="settings-row-label">Improve the model</span>
                    <button
                      class="settings-switch"
                      :class="{ 'is-on': improveModel }"
                      type="button"
                      role="switch"
                      :aria-checked="improveModel"
                      aria-label="Improve the model"
                      @click="improveModel = !improveModel"
                    >
                      <span
                        class="settings-switch-thumb"
                        aria-hidden="true"
                      />
                    </button>
                  </div>

                  <div class="settings-row">
                    <span class="settings-row-label">Storage location</span>
                    <span class="settings-value">Local device</span>
                  </div>
                </div>
              </section>

              <section
                v-else
                id="settings-section-about"
                class="settings-section"
                role="tabpanel"
                aria-labelledby="settings-tab-about"
              >
                <h3 class="settings-section-title">About</h3>

                <div class="settings-list">
                  <div class="settings-row">
                    <span class="settings-row-label">Product</span>
                    <span class="settings-value">OpenGPT</span>
                  </div>

                  <div class="settings-row">
                    <span class="settings-row-label">Version</span>
                    <span class="settings-value">Preview</span>
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

<style scoped>
@reference "../styles/index.css";

.settings-modal-layer {
  @apply fixed inset-0 grid;

  z-index: 100;
  place-items: end;
  background: var(--color-overlay);
}

.settings-modal {
  @apply flex w-full flex-col overflow-hidden;

  height: min(92dvh, 760px);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  background: var(--color-surface);
  color: var(--color-text);
}

.settings-modal-header {
  @apply flex shrink-0 items-center justify-between gap-4;

  min-height: 3.25rem;
  padding: 0.25rem 0.75rem 0.25rem 1.25rem;
}

.settings-modal-title {
  @apply m-0 font-semibold;

  font-size: 0.95rem;
  letter-spacing: -0.02em;
}

.settings-close-button {
  @apply inline-flex size-9 items-center justify-center;

  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
  transition:
    color 150ms ease,
    background-color 150ms ease;
}

.settings-close-button:hover {
  background: var(--color-surface-muted);
  color: var(--color-text);
}

.settings-close-icon {
  @apply shrink-0;
}

.settings-layout {
  @apply grid min-h-0 flex-1;

  grid-template-rows: auto minmax(0, 1fr);
}

.settings-navigation {
  @apply flex min-w-0 overflow-x-auto;

  gap: 0.125rem;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--color-border-subtle);
}

.settings-navigation-button {
  @apply flex shrink-0 items-center gap-2 text-left font-normal;

  min-height: 2rem;
  padding: 0 0.625rem;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
  font-size: 0.88rem;
  transition:
    color 150ms ease,
    background-color 150ms ease;
}

.settings-navigation-button:hover {
  background: var(--color-surface-muted);
  color: var(--color-text);
}

.settings-navigation-button.is-active {
  @apply font-semibold;

  color: var(--color-text);
}

.settings-navigation-icon {
  @apply shrink-0;

  width: 1.1rem;
  height: 1.1rem;
}

.settings-navigation-label {
  @apply whitespace-nowrap;
}

.settings-content {
  @apply h-full min-h-0 min-w-0 overflow-y-auto;

  padding: 1rem 1rem 1.5rem;
  background: var(--color-surface);
}

.settings-section {
  @apply grid min-w-0 gap-5;
}

.settings-section-title {
  @apply m-0 text-base font-semibold;

  letter-spacing: -0.02em;
}

.settings-list {
  @apply grid min-w-0;
}

.settings-row {
  @apply flex items-center justify-between gap-5 border-b py-3 text-sm;

  min-height: 3rem;
  border-color: var(--color-border-subtle);
}

.settings-row-label {
  @apply min-w-0;
}

.settings-select {
  @apply h-8 min-w-28 text-right text-sm;

  max-width: 55%;
  background: transparent;
  color: var(--color-text-muted);
}

.settings-select:hover,
.settings-select:focus {
  color: var(--color-text);
}

.settings-select-option {
  color: var(--color-text);
}

.settings-switch {
  @apply relative h-6 w-10 shrink-0 rounded-full;

  background: var(--color-surface-emphasis);
  transition: background-color 140ms ease;
}

.settings-switch.is-on {
  background: var(--color-action-primary);
}

.settings-switch-thumb {
  @apply absolute rounded-full;

  top: 3px;
  left: 3px;
  width: 18px;
  height: 18px;
  background: var(--color-on-action);
  transition: transform 140ms ease;
}

.settings-switch.is-on .settings-switch-thumb {
  transform: translateX(16px);
}

.settings-value {
  @apply text-right;

  color: var(--color-text-muted);
}

.settings-login-link {
  @apply font-medium underline;

  text-underline-offset: 2px;
}

.settings-modal-transition-enter-active {
  transition: opacity 150ms ease-out;
}

.settings-modal-transition-leave-active {
  transition: opacity 150ms ease-in;
}

.settings-modal-transition-enter-from,
.settings-modal-transition-leave-to {
  opacity: 0;
}

@media (min-width: 768px) {
  .settings-modal-layer {
    @apply p-6;

    place-items: center;
  }

  .settings-modal {
    max-width: 860px;
    height: min(640px, calc(100dvh - 48px));
    border-radius: var(--radius-lg);
  }

  .settings-layout {
    grid-template-rows: 1fr;
    grid-template-columns: minmax(150px, 2fr) minmax(0, 8fr);
  }

  .settings-navigation {
    @apply h-full flex-col overflow-y-auto;

    border-right: 1px solid var(--color-border-subtle);
    border-bottom: 0;
  }

  .settings-navigation-button {
    @apply w-full;

    min-height: 2.25rem;
  }

  .settings-content {
    padding: 1.25rem 1.75rem 1.75rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  .settings-close-button,
  .settings-navigation-button,
  .settings-switch,
  .settings-switch-thumb,
  .settings-modal-transition-enter-active,
  .settings-modal-transition-leave-active {
    transition: none;
  }
}
</style>
