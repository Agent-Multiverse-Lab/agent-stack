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
  Image as ImageIcon,
  Layers,
  Library,
  LogIn,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Settings,
  SquarePen,
  SquareTerminal
} from "@lucide/vue"
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router"

import logoUrl from "@/assets/logo.svg"
import ConversationSearchComponent from "@/components/ConversationSearchComponent.vue"
import SettingsComponent from "@/components/SettingsComponent.vue"
import { useLocalChat } from "@/composables/useLocalChat"
import type { FeatureId } from "@/types/feature"

const route = useRoute()
const router = useRouter()
const {
  conversations,
  activeConversationId,
  selectConversation,
  startNewConversation
} = useLocalChat()

const sidebarCollapsed = ref(false)
const mobileSidebarOpen = ref(false)
const searchOpen = ref(false)
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
  { id: "image", label: "Image", icon: ImageIcon },
  { id: "static", label: "Static", icon: Layers },
  { id: "sandbox", label: "Sandbox", icon: SquareTerminal }
]

const pageTitle = computed(() => {
  if (route.name === "feature") {
    return (
      featureLinks.find((feature) => feature.id === route.params.featureId)
        ?.label ?? "Feature"
    )
  }

  return typeof route.meta.title === "string" ? route.meta.title : "Chat"
})
const isChatRoute = computed(
  () => route.name === "chat" || route.name === "conversation"
)
const sidebarVisible = computed(() =>
  isNarrowViewport.value
    ? mobileSidebarOpen.value
    : !sidebarCollapsed.value
)
const selectedConversationId = computed(() =>
  route.name === "conversation" ? activeConversationId.value : null
)

const isFeatureActive = (featureId: FeatureId | "knowledge") =>
  featureId === "knowledge"
    ? route.name === "knowledge"
    : route.name === "feature" && route.params.featureId === featureId

const formatUpdatedAt = (value: string) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric"
  }).format(date)
}

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
  startNewConversation()
  mobileSidebarOpen.value = false

  if (route.name !== "chat") {
    await router.push({ name: "chat" })
  }
}

const selectConversationLink = (conversationId: string) => {
  selectConversation(conversationId)
  mobileSidebarOpen.value = false
}

const openConversation = async (conversationId: string) => {
  selectConversationLink(conversationId)
  await router.push({
    name: "conversation",
    params: { conversationId }
  })
}

const openSearch = () => {
  settingsOpen.value = false
  searchOpen.value = true
}

const openSettings = () => {
  searchOpen.value = false
  settingsOpen.value = true
}
</script>

<template>
  <div class="navigation-view">
    <aside
      class="navigation-sidebar"
      :class="{
        'is-desktop-open':
          !isNarrowViewport && !sidebarCollapsed,
        'is-desktop-collapsed': !isNarrowViewport && sidebarCollapsed,
        'is-mobile-open': isNarrowViewport && mobileSidebarOpen,
        'is-mobile-closed': isNarrowViewport && !mobileSidebarOpen
      }"
      aria-label="Application navigation"
    >
      <div class="navigation-sidebar-content">
        <header class="navigation-sidebar-header">
          <RouterLink
            class="navigation-brand"
            :to="{ name: 'chat' }"
            aria-label="OpenGPT home"
            @click="openNewConversation"
          >
            <img
              :src="logoUrl"
              class="navigation-brand-logo"
              alt=""
            >
            <span class="navigation-brand-name">OpenGPT</span>
          </RouterLink>

          <button
            v-if="isNarrowViewport"
            class="navigation-mobile-close"
            type="button"
            aria-label="Close sidebar"
            @click="mobileSidebarOpen = false"
          >
            <PanelLeftClose
              class="navigation-mobile-close-icon"
              :size="18"
              :stroke-width="1.8"
              aria-hidden="true"
            />
          </button>
        </header>

        <nav class="navigation-primary" aria-label="Primary navigation">
          <div class="navigation-link-group">
            <button
              class="navigation-action"
              type="button"
              @click="openNewConversation"
            >
              <SquarePen
                class="navigation-link-icon"
                :size="18"
                :stroke-width="1.8"
                aria-hidden="true"
              />
              <span class="navigation-link-label">New chat</span>
            </button>
            <button
              class="navigation-action"
              type="button"
              :class="{ 'is-active': searchOpen }"
              @click="openSearch"
            >
              <Search
                class="navigation-link-icon"
                :size="18"
                :stroke-width="1.8"
                aria-hidden="true"
              />
              <span class="navigation-link-label">Search chats</span>
            </button>
          </div>

          <div class="navigation-link-group" aria-label="Features">
            <RouterLink
              v-for="featureLink in featureLinks"
              :key="featureLink.id"
              class="navigation-feature-link"
              :class="{
                'is-active': isFeatureActive(featureLink.id)
              }"
              :to="
                featureLink.id === 'knowledge'
                  ? { name: 'knowledge' }
                  : {
                    name: 'feature',
                    params: { featureId: featureLink.id }
                  }
              "
              @click="mobileSidebarOpen = false"
            >
              <component
                :is="featureLink.icon"
                class="navigation-link-icon"
                :size="18"
                :stroke-width="isFeatureActive(featureLink.id) ? 2 : 1.8"
                aria-hidden="true"
              />
              <span class="navigation-link-label">
                {{ featureLink.label }}
              </span>
            </RouterLink>
          </div>
        </nav>

        <section
          class="navigation-conversations"
          aria-labelledby="conversation-list-title"
        >
          <h2
            id="conversation-list-title"
            class="navigation-conversations-heading"
          >
            Chats
          </h2>

          <div
            v-if="conversations.length"
            class="navigation-conversation-list"
          >
            <RouterLink
              v-for="conversation in conversations"
              :key="conversation.id"
              class="navigation-conversation-link"
              :class="{
                'is-active':
                  conversation.id === selectedConversationId
              }"
              :to="{
                name: 'conversation',
                params: { conversationId: conversation.id }
              }"
              :aria-current="
                conversation.id === selectedConversationId ? 'page' : undefined
              "
              :title="conversation.title || 'Untitled conversation'"
              @click="selectConversationLink(conversation.id)"
            >
              <span class="navigation-conversation-title">
                {{ conversation.title || "Untitled conversation" }}
              </span>
              <span class="navigation-conversation-date">
                {{ formatUpdatedAt(conversation.updatedAt) }}
              </span>
            </RouterLink>
          </div>

          <p v-else class="navigation-conversations-empty">
            No conversations
          </p>
        </section>

        <footer class="navigation-sidebar-footer">
          <RouterLink
            class="navigation-footer-action"
            to="/login"
          >
            <LogIn
              class="navigation-footer-icon"
              :size="17"
              :stroke-width="1.8"
              aria-hidden="true"
            />
            <span class="navigation-footer-label">Log in</span>
          </RouterLink>
          <button
            class="navigation-footer-action"
            type="button"
            @click="openSettings"
          >
            <Settings
              class="navigation-footer-icon"
              :size="17"
              :stroke-width="1.8"
              aria-hidden="true"
            />
            <span class="navigation-footer-label">Settings</span>
          </button>
        </footer>
      </div>
    </aside>

    <button
      v-if="isNarrowViewport && mobileSidebarOpen"
      class="navigation-drawer-backdrop"
      type="button"
      aria-label="Close sidebar"
      @click="mobileSidebarOpen = false"
    />

    <main class="navigation-main">
      <header class="navigation-topbar">
        <div class="navigation-page-identity">
          <button
            class="navigation-sidebar-toggle"
            type="button"
            :aria-label="sidebarVisible ? 'Collapse sidebar' : 'Expand sidebar'"
            :title="sidebarVisible ? 'Collapse sidebar' : 'Expand sidebar'"
            @click="toggleSidebar"
          >
            <PanelLeftClose
              v-if="sidebarVisible"
              class="navigation-sidebar-toggle-icon"
              :size="19"
              :stroke-width="1.8"
              aria-hidden="true"
            />
            <PanelLeftOpen
              v-else
              class="navigation-sidebar-toggle-icon"
              :size="19"
              :stroke-width="1.8"
              aria-hidden="true"
            />
          </button>
          <h1 class="navigation-page-title">
            {{ pageTitle }}
          </h1>
        </div>

        <nav
          class="navigation-account-actions"
          aria-label="Account actions"
        >
          <button
            v-if="isChatRoute"
            class="navigation-new-chat"
            type="button"
            aria-label="New chat"
            title="New chat"
            @click="openNewConversation"
          >
            <SquarePen
              class="navigation-new-chat-icon"
              :size="17"
              :stroke-width="1.8"
              aria-hidden="true"
            />
          </button>
          <RouterLink
            class="navigation-login-link"
            to="/login"
          >
            Log in
          </RouterLink>
          <RouterLink
            class="navigation-signup-link"
            to="/register"
          >
            <span class="navigation-signup-full">Sign up for free</span>
            <span class="navigation-signup-short">Sign up</span>
          </RouterLink>
        </nav>
      </header>

      <div class="navigation-route-content">
        <RouterView />
      </div>
    </main>
  </div>

  <ConversationSearchComponent
    :open="searchOpen"
    :conversations="conversations"
    @close="searchOpen = false"
    @select="openConversation"
  />

  <SettingsComponent
    :open="settingsOpen"
    @close="settingsOpen = false"
  />
</template>

<style scoped>
@reference "../styles/index.css";

.navigation-view {
  @apply flex h-dvh w-full overflow-hidden;

  color: var(--color-text);
  background: var(--color-canvas);
}

.navigation-sidebar {
  @apply relative z-20 h-full shrink-0 overflow-hidden;

  background: var(--color-surface-muted);
  transition:
    width 200ms ease-out,
    flex-basis 200ms ease-out,
    transform 200ms ease-out;
}

.navigation-sidebar.is-desktop-open {
  width: var(--sidebar-width);
  flex-basis: var(--sidebar-width);
}

.navigation-sidebar.is-desktop-collapsed {
  width: 0;
  flex-basis: 0;
}

.navigation-sidebar-content {
  @apply flex h-full flex-col overflow-hidden;

  width: var(--sidebar-width);
  min-width: var(--sidebar-width);
}

.navigation-sidebar-header {
  @apply flex items-center justify-between px-4;

  min-height: 3.25rem;
  padding-top: 0.75rem;
  padding-bottom: 0.25rem;
}

.navigation-brand {
  @apply inline-flex min-w-0 items-center gap-2 font-semibold;

  letter-spacing: -0.02em;
}

.navigation-brand-logo {
  width: 1.15rem;
  height: 1.15rem;
}

.navigation-brand-name,
.navigation-page-title,
.navigation-conversation-title {
  @apply overflow-hidden text-ellipsis whitespace-nowrap;
}

.navigation-brand-name {
  font-size: 0.95rem;
}

.navigation-mobile-close,
.navigation-sidebar-toggle,
.navigation-new-chat {
  @apply grid shrink-0 place-items-center;

  width: 2.25rem;
  height: 2.25rem;
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  background: transparent;
}

.navigation-mobile-close {
  width: 2rem;
  height: 2rem;
}

.navigation-mobile-close:hover,
.navigation-sidebar-toggle:hover,
.navigation-new-chat:hover {
  color: var(--color-text);
  background: var(--color-surface-muted);
}

.navigation-mobile-close:hover {
  background: var(--color-surface-hover);
}

.navigation-primary {
  @apply grid;

  gap: 0.5rem;
  padding: 0.125rem 0.375rem 0.5rem;
}

.navigation-link-group,
.navigation-sidebar-footer {
  @apply grid;

  gap: 1px;
}

.navigation-action,
.navigation-feature-link {
  @apply grid w-full items-center text-sm;

  min-height: 2.25rem;
  grid-template-columns: 22px minmax(0, 1fr);
  gap: 0.5rem;
  padding-inline: 0.625rem;
  border-radius: var(--radius-sm);
  background: transparent;
}

.navigation-action {
  @apply text-left;
}

.navigation-action:hover,
.navigation-feature-link:hover,
.navigation-action.is-active,
.navigation-feature-link.is-active {
  background: var(--color-surface-hover);
}

.navigation-action.is-active,
.navigation-feature-link.is-active {
  @apply font-semibold;
}

.navigation-link-icon {
  @apply shrink-0;
}

.navigation-conversations {
  @apply flex min-h-0 flex-1 flex-col;

  padding: 0 0.375rem 0.75rem;
}

.navigation-conversations-heading {
  @apply m-0 font-medium;

  min-height: 1.75rem;
  padding: 0.375rem 0.625rem;
  color: var(--color-text-subtle);
  font-size: 0.75rem;
  letter-spacing: 0.02em;
}

.navigation-conversation-list {
  @apply min-h-0 overflow-y-auto overscroll-contain;
}

.navigation-conversation-link {
  @apply flex w-full min-w-0 items-center justify-between overflow-hidden text-sm;

  min-height: 2.25rem;
  gap: 0.5rem;
  padding: 0.5rem 0.625rem;
  border-radius: var(--radius-sm);
}

.navigation-conversation-link:hover {
  background: var(--color-surface-hover);
}

.navigation-conversation-link.is-active {
  @apply font-semibold;
}

.navigation-conversation-title {
  @apply min-w-0;
}

.navigation-conversation-date {
  @apply shrink-0 font-normal;

  color: var(--color-text-subtle);
  font-size: 0.68rem;
  opacity: 0;
  transition: opacity 120ms ease;
}

.navigation-conversation-link:hover .navigation-conversation-date,
.navigation-conversation-link:focus-visible .navigation-conversation-date {
  opacity: 1;
}

.navigation-conversations-empty {
  @apply m-0 text-sm;

  padding: 0.25rem 0.625rem;
  color: var(--color-text-subtle);
}

.navigation-sidebar-footer {
  padding: 0.25rem 0.375rem 0.75rem;
}

.navigation-footer-action {
  @apply flex items-center gap-2 text-left text-sm;

  min-height: 2.25rem;
  padding-inline: 0.625rem;
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  background: transparent;
}

.navigation-footer-action:hover {
  color: var(--color-text);
  background: var(--color-surface-hover);
}

.navigation-drawer-backdrop {
  @apply fixed inset-0 z-40;

  background: var(--color-overlay);
}

.navigation-main {
  @apply flex min-w-0 flex-1 flex-col overflow-hidden;
}

.navigation-topbar {
  @apply flex shrink-0 items-center justify-between gap-4 py-2;

  min-height: 52px;
  padding-inline: clamp(0.75rem, 2vw, 1.25rem);
}

.navigation-page-identity,
.navigation-account-actions {
  @apply flex min-w-0 items-center;

  gap: 0.375rem;
}

.navigation-page-title {
  @apply m-0 text-base font-semibold;

  letter-spacing: -0.02em;
}

.navigation-new-chat {
  opacity: 0;
  pointer-events: none;
  transition:
    color 120ms ease,
    background-color 120ms ease,
    opacity 120ms ease;
}

.navigation-topbar:hover .navigation-new-chat,
.navigation-topbar:focus-within .navigation-new-chat {
  opacity: 1;
  pointer-events: auto;
}

.navigation-login-link,
.navigation-signup-link {
  @apply inline-flex items-center px-3 font-medium;

  min-height: 34px;
  border-radius: var(--radius-sm);
  font-size: 13px;
}

.navigation-login-link {
  color: var(--color-text-muted);
}

.navigation-login-link:hover {
  color: var(--color-text);
  background: var(--color-surface-muted);
}

.navigation-signup-link {
  color: var(--color-on-action);
  background: var(--color-action-primary);
}

.navigation-signup-link:hover {
  background: var(--color-action-primary-hover);
}

.navigation-signup-short {
  @apply hidden;
}

.navigation-route-content {
  @apply min-h-0 flex-1 overflow-hidden;
}

@media (max-width: 900px) {
  .navigation-sidebar {
    @apply fixed inset-y-0 left-0 z-50;

    width: min(86vw, 19rem);
    flex-basis: auto;
  }

  .navigation-sidebar.is-mobile-open {
    transform: translateX(0);
  }

  .navigation-sidebar.is-mobile-closed {
    transform: translateX(-102%);
  }

  .navigation-sidebar-content {
    width: min(86vw, 19rem);
    min-width: min(86vw, 19rem);
  }
}

@media (max-width: 560px) {
  .navigation-login-link,
  .navigation-signup-full {
    @apply hidden;
  }

  .navigation-signup-short {
    display: inline;
  }
}

@media (hover: none) {
  .navigation-new-chat {
    opacity: 1;
    pointer-events: auto;
  }
}
</style>
