<script setup lang="ts">
import { ref, watch } from "vue"
import { StickyNote, X } from "@lucide/vue"
import type { CreateNotePayload } from "@/types/library"

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: "close"): void
  (e: "create", payload: CreateNotePayload): void
}>()

const title = ref("")
const content = ref("")

watch(
  () => props.open,
  (val) => {
    if (val) {
      title.value = ""
      content.value = ""
    }
  }
)

const handleSubmit = () => {
  const trimmedTitle = title.value.trim()
  if (!trimmedTitle) return
  emit("create", {
    title: trimmedTitle,
    content: content.value.trim()
  })
  emit("close")
}
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center bg-graphite/40 backdrop-blur-xs p-4"
    @click.self="emit('close')"
  >
    <div class="w-full max-w-md overflow-hidden rounded-xl border border-graphite/12 bg-paper p-5 shadow-lg">
      <div class="flex items-center justify-between pb-3 border-b border-graphite/8">
        <div class="flex items-center gap-2">
          <StickyNote :size="18" class="text-graphite" />
          <h3 class="m-0 text-sm font-semibold text-graphite">Create Quick Note</h3>
        </div>
        <button
          type="button"
          class="grid h-6 w-6 place-items-center rounded-md text-slate hover:bg-mist hover:text-graphite"
          @click="emit('close')"
        >
          <X :size="14" />
        </button>
      </div>

      <form class="mt-4 flex flex-col gap-3" @submit.prevent="handleSubmit">
        <div>
          <label class="block text-xs font-medium text-slate mb-1">Title</label>
          <input
            v-model="title"
            type="text"
            placeholder="Note title..."
            class="w-full h-9 rounded-md border border-graphite/14 bg-mist/40 px-3 text-xs text-graphite focus:border-graphite/30 focus:bg-paper focus:outline-none focus:ring-1 focus:ring-graphite/20"
            autofocus
            required
          >
        </div>

        <div>
          <label class="block text-xs font-medium text-slate mb-1">Content</label>
          <textarea
            v-model="content"
            rows="4"
            placeholder="Write your note content here..."
            class="w-full rounded-md border border-graphite/14 bg-mist/40 p-3 text-xs text-graphite focus:border-graphite/30 focus:bg-paper focus:outline-none focus:ring-1 focus:ring-graphite/20 resize-none"
          />
        </div>

        <div class="flex items-center justify-end gap-2 pt-2">
          <button
            type="button"
            class="h-8 rounded-md px-3 text-xs font-medium text-slate hover:bg-mist"
            @click="emit('close')"
          >
            Cancel
          </button>
          <button
            type="submit"
            class="h-8 rounded-md bg-graphite px-4 text-xs font-medium text-paper hover:bg-graphite/90"
          >
            Save Note
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
