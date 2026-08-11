<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue"
import { ChevronRight, Paperclip, Plus } from "@lucide/vue"

defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits<{
  "select-attachment": []
}>()

const isOpen = ref(false)
const containerRef = ref<HTMLDivElement | null>(null)

const toggleMenu = () => {
  isOpen.value = !isOpen.value
}

const closeMenu = () => {
  isOpen.value = false
}

const handleSelectAttachment = () => {
  closeMenu()
  emit("select-attachment")
}

const handleClickOutside = (event: MouseEvent) => {
  if (isOpen.value && containerRef.value && !containerRef.value.contains(event.target as Node)) {
    closeMenu()
  }
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === "Escape" && isOpen.value) {
    closeMenu()
  }
}

onMounted(() => {
  window.addEventListener("click", handleClickOutside)
  window.addEventListener("keydown", handleKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener("click", handleClickOutside)
  window.removeEventListener("keydown", handleKeydown)
})
</script>

<template>
  <div
    ref="containerRef"
    class="static"
  >
    <!-- Trigger Button -->
    <button
      class="grid size-10 shrink-0 place-items-center rounded-full bg-graphite/6 text-graphite transition-all duration-150 hover:bg-graphite/10 disabled:cursor-not-allowed disabled:text-graphite/25 motion-reduce:transition-none"
      type="button"
      :disabled="disabled"
      :aria-expanded="isOpen"
      aria-haspopup="true"
      aria-label="Action menu"
      title="Action menu"
      @click.stop="toggleMenu"
    >
      <Plus
        :size="19"
        :stroke-width="1.9"
        class="transition-transform duration-200 motion-reduce:transition-none"
        :class="{ 'rotate-45': isOpen }"
        aria-hidden="true"
      />
    </button>

    <!-- Floating Full-Width Action Menu Panel Below Input Box -->
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="transform scale-[0.98] opacity-0 -translate-y-1"
      enter-to-class="transform scale-100 opacity-100 translate-y-0"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="transform scale-100 opacity-100 translate-y-0"
      leave-to-class="transform scale-[0.98] opacity-0 -translate-y-1"
    >
      <div
        v-if="isOpen"
        class="absolute top-full left-0 right-0 z-50 mt-2 w-full overflow-hidden rounded-[16px] border border-graphite/14 bg-paper/95 p-2 shadow-[0_16px_36px_rgba(13,13,13,0.12)] backdrop-blur-md motion-reduce:transition-none"
        role="menu"
        aria-orientation="vertical"
        aria-label="Actions menu"
      >
        <button
          type="button"
          class="flex w-full items-center justify-between rounded-[12px] px-4 py-3 text-sm font-medium text-graphite transition-colors duration-150 hover:bg-graphite/8 active:bg-graphite/12 motion-reduce:transition-none"
          role="menuitem"
          @click="handleSelectAttachment"
        >
          <span class="flex items-center gap-3">
            <Paperclip
              :size="19"
              :stroke-width="2"
              class="shrink-0 text-graphite/80"
              aria-hidden="true"
            />
            <span>添加附件</span>
          </span>
          <ChevronRight
            :size="16"
            class="shrink-0 text-graphite/40"
            aria-hidden="true"
          />
        </button>
      </div>
    </Transition>
  </div>
</template>
