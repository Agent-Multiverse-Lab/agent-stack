<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from "vue"
import { useRouter } from "vue-router"
import { Loader2, MessageSquare, Search, X } from "@lucide/vue"

import { listThreads } from "@/api/agent"
import type { ThreadSummaryResponse } from "@/types/chat"

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const router = useRouter()

const query = ref("")
const inputRef = ref<HTMLInputElement | null>(null)
const threads = ref<ThreadSummaryResponse[]>([])
const loading = ref(false)
const loadingMore = ref(false)
const nextCursor = ref<string | null>(null)
const hasMore = ref(false)

let debounceTimer: ReturnType<typeof setTimeout> | null = null

const close = () => {
  query.value = ""
  threads.value = []
  nextCursor.value = null
  hasMore.value = false
  emit("close")
}

const fetchThreads = async (searchQuery: string, cursor?: string) => {
  const isInitial = !cursor
  if (isInitial) {
    loading.value = true
  } else {
    loadingMore.value = true
  }

  try {
    const res = await listThreads({
      query: searchQuery.trim() || undefined,
      cursor,
      limit: 15
    })

    if (isInitial) {
      threads.value = res.items
    } else {
      threads.value.push(...res.items)
    }

    nextCursor.value = res.next_cursor
    hasMore.value = res.has_more
  } catch (err) {
    console.error("Failed to load threads:", err)
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

const loadMore = () => {
  if (!hasMore.value || loadingMore.value || !nextCursor.value) return
  void fetchThreads(query.value, nextCursor.value)
}

const onQueryInput = () => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    void fetchThreads(query.value)
  }, 250)
}

const selectThread = async (threadId: string) => {
  close()
  await router.push({
    name: "conversation",
    params: { threadId }
  })
}

const onKeydown = (event: KeyboardEvent) => {
  if (event.key === "Escape") close()
}

watch(
  () => props.open,
  (isOpen) => {
    document.body.toggleAttribute("data-modal-open", isOpen)
    if (isOpen) {
      document.addEventListener("keydown", onKeydown)
      void fetchThreads("")
      void nextTick(() => {
        inputRef.value?.focus()
      })
      return
    }
    document.removeEventListener("keydown", onKeydown)
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
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
        class="fixed inset-0 z-[100] grid place-items-start justify-center bg-graphite/36 p-4 pt-[10dvh]"
        @mousedown.self="close"
      >
        <div
          class="flex h-[min(60vh,620px)] w-[min(84vw,980px)] max-w-[980px] flex-col overflow-hidden rounded-2xl bg-paper text-graphite shadow-2xl ring-1 ring-graphite/10"
          role="dialog"
          aria-modal="true"
          aria-label="Search conversation threads"
        >
          <!-- 1. Upper Search Bar (上部横条大搜索框) -->
          <div class="flex items-center gap-4 border-b border-graphite/10 px-6 py-5">
            <Search class="h-6 w-6 shrink-0 text-slate" aria-hidden="true" />
            <input
              ref="inputRef"
              v-model="query"
              type="text"
              class="w-full bg-transparent text-lg text-graphite placeholder:text-slate/60 focus:outline-none"
              placeholder="Search conversation"
              @input="onQueryInput"
            />
            <button
              v-if="query"
              class="grid size-7 shrink-0 place-items-center rounded-md bg-transparent text-slate hover:bg-mist hover:text-graphite"
              type="button"
              aria-label="Clear search"
              @click="query = ''; onQueryInput()"
            >
              <X class="h-5 w-5" aria-hidden="true" />
            </button>
          </div>

          <!-- 2. Lower Data Area (下部大容量纯标题列表) -->
          <div class="flex-1 overflow-y-auto p-4">
            <!-- Loading State -->
            <div v-if="loading" class="flex items-center justify-center gap-2 py-16 text-base text-slate">
              <Loader2 class="h-5 w-5 animate-spin text-slate" />
              <span>Searching conversations...</span>
            </div>

            <!-- Empty State -->
            <div
              v-else-if="threads.length === 0"
              class="py-16 text-center text-base text-slate"
            >
              No matching conversation titles found.
            </div>

            <!-- Title-Only Conversation List -->
            <div v-else class="grid gap-1.5">
              <button
                v-for="item in threads"
                :key="item.thread_id"
                class="group flex w-full items-center gap-3.5 rounded-xl px-4 py-3.5 text-left text-base transition-colors hover:bg-mist"
                type="button"
                @click="selectThread(item.thread_id)"
              >
                <MessageSquare class="h-5 w-5 shrink-0 text-slate/70 group-hover:text-graphite" />
                <span class="truncate font-medium text-graphite">{{ item.title || 'Untitled Conversation' }}</span>
              </button>

              <!-- Pagination / Load More Button -->
              <div v-if="hasMore" class="pt-2 text-center">
                <button
                  class="inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-xs text-slate hover:bg-mist hover:text-graphite"
                  type="button"
                  :disabled="loadingMore"
                  @click="loadMore"
                >
                  <Loader2 v-if="loadingMore" class="h-3.5 w-3.5 animate-spin" />
                  <span>{{ loadingMore ? 'Loading more...' : 'Load more conversations' }}</span>
                </button>
              </div>
            </div>
          </div>

        
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
