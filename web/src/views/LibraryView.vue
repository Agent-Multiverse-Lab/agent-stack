<script setup lang="ts">
import { computed, ref } from "vue"
import { message } from "ant-design-vue"
import CreateFolderComponent from "@/components/library/CreateFolderComponent.vue"
import CreateNoteComponent from "@/components/library/CreateNoteComponent.vue"
import LibraryFileListComponent from "@/components/library/LibraryFileListComponent.vue"
import LibraryFilterComponent from "@/components/library/LibraryFilterComponent.vue"
import LibraryHeaderComponent from "@/components/library/LibraryHeaderComponent.vue"
import { generateMoreMockItems, INITIAL_MOCK_ITEMS } from "@/components/library/mockData"
import type {
  CreateNotePayload,
  LibraryCategory,
  LibraryItem,
  LibraryItemSource,
  LibraryItemType,
  LibraryViewMode
} from "@/types/library"

const items = ref<LibraryItem[]>([...INITIAL_MOCK_ITEMS])
const searchQuery = ref("")
const category = ref<LibraryCategory>("all")
const fileType = ref<LibraryItemType | "all">("all")
const source = ref<LibraryItemSource | "all">("all")
// Default view mode set strictly to list
const viewMode = ref<LibraryViewMode>("list")

// Modals
const createFolderOpen = ref(false)
const createNoteOpen = ref(false)

// Infinite loading pagination - Strictly limit to Max 10 items initially displayed
const PAGE_SIZE = 10
const displayedLimit = ref(PAGE_SIZE)
const isLoadingMore = ref(false)

const filteredItems = computed(() => {
  return items.value.filter((item) => {
    // Search Filter
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.toLowerCase().trim()
      const nameMatch = item.name.toLowerCase().includes(q)
      const noteMatch = item.noteContent?.toLowerCase().includes(q) ?? false
      if (!nameMatch && !noteMatch) return false
    }

    // Top Row Category Tab Filter (All, Images, Documents)
    if (category.value === "images") {
      if (item.type !== "image") return false
    } else if (category.value === "documents") {
      if (!["document", "spreadsheet", "presentation", "note"].includes(item.type)) {
        return false
      }
    }

    // Detailed Type Dropdown Filter
    if (fileType.value !== "all") {
      if (item.type !== fileType.value) return false
    }

    // Source Filter
    if (source.value !== "all") {
      if (item.source !== source.value) return false
    }

    return true
  })
})

const visibleItems = computed(() => {
  return filteredItems.value.slice(0, displayedLimit.value)
})

const hasMore = computed(() => {
  return displayedLimit.value < filteredItems.value.length
})

const handleLoadMore = () => {
  if (isLoadingMore.value || !hasMore.value) return

  isLoadingMore.value = true
  setTimeout(() => {
    if (displayedLimit.value < filteredItems.value.length) {
      displayedLimit.value += PAGE_SIZE
    }
    isLoadingMore.value = false
  }, 400)
}

const handleUploadFiles = (files: FileList) => {
  const newItems: LibraryItem[] = Array.from(files).map((file, idx) => {
    let type: LibraryItemType = "document"
    if (file.type.startsWith("image/")) type = "image"
    else if (file.name.endsWith(".xlsx") || file.name.endsWith(".csv")) type = "spreadsheet"
    else if (file.name.endsWith(".pptx") || file.name.endsWith(".ppt")) type = "presentation"

    return {
      id: `uploaded-${Date.now()}-${idx}`,
      name: file.name,
      type,
      source: "uploaded",
      sizeBytes: file.size,
      mimeType: file.type,
      updatedAt: new Date().toISOString().replace("T", " ").substring(0, 16),
      createdAt: new Date().toISOString().replace("T", " ").substring(0, 16)
    }
  })

  items.value.unshift(...newItems)
  message.success(`Successfully uploaded ${newItems.length} file(s)`)
}

const handleCreateFolder = (folderName: string) => {
  const newFolder: LibraryItem = {
    id: `folder-${Date.now()}`,
    name: folderName,
    type: "folder",
    source: "uploaded",
    sizeBytes: 0,
    itemCount: 0,
    updatedAt: new Date().toISOString().replace("T", " ").substring(0, 16),
    createdAt: new Date().toISOString().replace("T", " ").substring(0, 16)
  }

  items.value.unshift(newFolder)
  message.success(`Folder "${folderName}" created`)
}

const handleCreateNote = (payload: CreateNotePayload) => {
  const newNote: LibraryItem = {
    id: `note-${Date.now()}`,
    name: payload.title,
    type: "note",
    source: "uploaded",
    sizeBytes: new Blob([payload.content]).size,
    noteContent: payload.content,
    updatedAt: new Date().toISOString().replace("T", " ").substring(0, 16),
    createdAt: new Date().toISOString().replace("T", " ").substring(0, 16)
  }

  items.value.unshift(newNote)
  message.success(`Note "${payload.title}" created`)
}

const handleDeleteItem = (id: string) => {
  items.value = items.value.filter((i) => i.id !== id)
  message.info("Item deleted")
}

const handleDownloadItem = (item: LibraryItem) => {
  message.info(`Downloading ${item.name}...`)
}
</script>

<template>
  <main class="flex h-full min-h-0 w-full justify-center bg-paper text-graphite" aria-label="Library">
    <!-- Centered Content Container with Spacious Breathing Room -->
    <div class="flex h-full min-h-0 w-full max-w-[920px] flex-col bg-paper">
      <!-- Row 1: Header Bar (Single Library title + icon, 16px search bar, Consolidated + New dropdown) -->
      <LibraryHeaderComponent
        v-model:search-query="searchQuery"
        @upload-files="handleUploadFiles"
        @open-create-folder="createFolderOpen = true"
        @open-create-note="createNoteOpen = true"
      />

      <!-- Row 2: Filter Toolbar (Expandable Sidebar trigger on hover/click, View mode switcher) -->
      <LibraryFilterComponent
        v-model:category="category"
        v-model:file-type="fileType"
        v-model:source="source"
        v-model:view-mode="viewMode"
      />

      <!-- Row 3: Bottom List Component (Default List Mode, Max 10 items, Name/Modified/Size columns, Hover-only actions) -->
      <LibraryFileListComponent
        :items="visibleItems"
        :view-mode="viewMode"
        :has-more="hasMore"
        :is-loading-more="isLoadingMore"
        @load-more="handleLoadMore"
        @delete-item="handleDeleteItem"
        @download-item="handleDownloadItem"
      />
    </div>

    <!-- Dialog Modals -->
    <CreateFolderComponent
      :open="createFolderOpen"
      @close="createFolderOpen = false"
      @create="handleCreateFolder"
    />

    <CreateNoteComponent
      :open="createNoteOpen"
      @close="createNoteOpen = false"
      @create="handleCreateNote"
    />
  </main>
</template>
