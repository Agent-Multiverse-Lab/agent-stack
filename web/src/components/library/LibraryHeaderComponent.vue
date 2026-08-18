<script setup lang="ts">
import { ref, watch } from "vue"
import {
  FolderPlus,
  Library,
  Plus,
  Search,
  StickyNote,
  Upload,
  X
} from "@lucide/vue"
import { Dropdown as ADropdown, Menu as AMenu, MenuItem as AMenuItem } from "ant-design-vue"

const props = defineProps<{
  searchQuery: string
}>()

const emit = defineEmits<{
  (e: "update:searchQuery", value: string): void
  (e: "upload-files", files: FileList): void
  (e: "open-create-folder"): void
  (e: "open-create-note"): void
}>()

const localSearch = ref(props.searchQuery)
const fileInputRef = ref<HTMLInputElement | null>(null)

watch(
  () => props.searchQuery,
  (newVal) => {
    localSearch.value = newVal
  }
)

const handleSearchInput = (e: Event) => {
  const target = e.target as HTMLInputElement
  localSearch.value = target.value
  emit("update:searchQuery", target.value)
}

const clearSearch = () => {
  localSearch.value = ""
  emit("update:searchQuery", "")
}

const triggerFileUpload = () => {
  fileInputRef.value?.click()
}

const onFileSelected = (e: Event) => {
  const target = e.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    emit("upload-files", target.files)
    target.value = ""
  }
}
</script>

<template>
  <!-- Header Row: Spacious Layout with Generous Breathing Room (py-4) -->
  <header class="flex flex-wrap items-center justify-between gap-4 bg-transparent px-4 py-4">
    <!-- Left Title: Clean Single Library Icon + Text -->
    <div class="flex items-center gap-2.5">
      <Library :size="22" :stroke-width="1.8" class="text-[#0F172A]" aria-hidden="true" />
      <h1 class="m-0 text-xl font-semibold tracking-[-0.02em] text-[#0F172A]">
        Library
      </h1>
    </div>

    <!-- Right Controls: Search bar (16px rounded, 14px text) & Consolidated + New Dropdown -->
    <div class="flex flex-wrap items-center gap-3">
      <!-- Search Bar with 16px Rounded Corners and 14px Text -->
      <div class="relative flex items-center">
        <Search
          class="pointer-events-none absolute left-3 text-[#64748B]"
          :size="16"
          :stroke-width="1.8"
          aria-hidden="true"
        />
        <input
          :value="localSearch"
          type="text"
          placeholder="Search..."
          class="h-9 w-48 rounded-[16px] bg-mist/70 pl-9 pr-8 text-sm text-[#0F172A] placeholder:text-[#94A3B8] transition-all focus:w-60 focus:bg-mist focus:outline-none"
          @input="handleSearchInput"
        >
        <button
          v-if="localSearch"
          type="button"
          class="absolute right-2.5 grid h-4 w-4 place-items-center rounded-full text-[#64748B] hover:text-[#0F172A]"
          aria-label="Clear search"
          @click="clearSearch"
        >
          <X :size="12" :stroke-width="2" aria-hidden="true" />
        </button>
      </div>

      <!-- Hidden File Input -->
      <input
        ref="fileInputRef"
        type="file"
        multiple
        class="hidden"
        @change="onFileSelected"
      >

      <!-- Consolidated + New Dropdown Button -->
      <ADropdown placement="bottomRight" trigger="click">
        <button
          type="button"
          class="inline-flex h-9 items-center gap-1.5 rounded-[16px] bg-[#0F172A] px-3.5 text-sm font-medium text-paper transition-all hover:bg-[#0F172A]/90 active:scale-[0.98]"
        >
          <Plus :size="15" :stroke-width="2" aria-hidden="true" />
          <span>New</span>
        </button>

        <template #overlay>
          <AMenu>
            <AMenuItem key="upload" @click="triggerFileUpload">
              <div class="flex items-center gap-2 px-1 py-0.5 text-xs">
                <Upload :size="14" />
                <span>Upload files</span>
              </div>
            </AMenuItem>
            <AMenuItem key="folder" @click="emit('open-create-folder')">
              <div class="flex items-center gap-2 px-1 py-0.5 text-xs">
                <FolderPlus :size="14" />
                <span>New folder</span>
              </div>
            </AMenuItem>
            <AMenuItem key="note" @click="emit('open-create-note')">
              <div class="flex items-center gap-2 px-1 py-0.5 text-xs">
                <StickyNote :size="14" />
                <span>Quick note</span>
              </div>
            </AMenuItem>
          </AMenu>
        </template>
      </ADropdown>
    </div>
  </header>
</template>
