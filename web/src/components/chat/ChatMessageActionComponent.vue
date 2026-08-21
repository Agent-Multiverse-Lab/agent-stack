<script setup lang="ts">
import { ref } from "vue"
import { Check, Copy, Layers, ThumbsDown, ThumbsUp } from "@lucide/vue"

const props = defineProps<{
  content: string
  hasSources?: boolean
}>()

const emit = defineEmits<{
  like: [type: "up" | "down" | null]
  copy: [content: string]
  source: []
}>()

const copied = ref(false)
const liked = ref<"up" | "down" | null>(null)

const handleCopy = async () => {
  if (!props.content) return
  try {
    await navigator.clipboard.writeText(props.content)
    copied.value = true
    emit("copy", props.content)
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch {
    // 忽略剪贴板写入异常
  }
}

const toggleLike = (type: "up" | "down") => {
  liked.value = liked.value === type ? null : type
  emit("like", liked.value)
}
</script>

<template>
  <div class="mt-2 flex items-center gap-1 text-slate">
    <button
      type="button"
      class="grid size-7 place-items-center rounded-md transition-colors hover:bg-graphite/6 hover:text-graphite"
      :class="{ 'text-emerald-600': copied }"
      :title="copied ? 'Copied' : 'Copy message'"
      :aria-label="copied ? 'Copied' : 'Copy message'"
      @click="handleCopy"
    >
      <Check v-if="copied" :size="14" :stroke-width="2" />
      <Copy v-else :size="14" :stroke-width="1.8" />
    </button>

    <button
      type="button"
      class="grid size-7 place-items-center rounded-md transition-colors hover:bg-graphite/6 hover:text-graphite"
      :class="{ 'bg-graphite/8 text-graphite': liked === 'up' }"
      title="Good response"
      aria-label="Good response"
      @click="toggleLike('up')"
    >
      <ThumbsUp :size="14" :stroke-width="1.8" />
    </button>

    <button
      type="button"
      class="grid size-7 place-items-center rounded-md transition-colors hover:bg-graphite/6 hover:text-graphite"
      :class="{ 'bg-graphite/8 text-graphite': liked === 'down' }"
      title="Bad response"
      aria-label="Bad response"
      @click="toggleLike('down')"
    >
      <ThumbsDown :size="14" :stroke-width="1.8" />
    </button>

    <button
      v-if="hasSources"
      type="button"
      class="inline-flex h-7 items-center gap-1 rounded-md px-1.5 text-xs font-medium transition-colors hover:bg-graphite/6 hover:text-graphite"
      title="View sources"
      aria-label="View sources"
      @click="emit('source')"
    >
      <Layers :size="13" :stroke-width="1.8" />
      <span>Sources</span>
    </button>
  </div>
</template>
