<script setup lang="ts">
import { computed } from "vue"
import {
  ChevronDown,
  FileText,
  Filter,
  Grid,
  Image as ImageIcon,
  Layers,
  LayoutList
} from "@lucide/vue"
import {
  Dropdown as ADropdown,
  Menu as AMenu,
  MenuItem as AMenuItem,
  Tooltip as ATooltip
} from "ant-design-vue"
import type {
  LibraryCategory,
  LibraryItemSource,
  LibraryItemType,
  LibraryViewMode
} from "@/types/library"

const props = defineProps<{
  category: LibraryCategory
  fileType: LibraryItemType | "all"
  source: LibraryItemSource | "all"
  viewMode: LibraryViewMode
}>()

const emit = defineEmits<{
  (e: "update:category", value: LibraryCategory): void
  (e: "update:fileType", value: LibraryItemType | "all"): void
  (e: "update:source", value: LibraryItemSource | "all"): void
  (e: "update:viewMode", value: LibraryViewMode): void
}>()

const categories: Array<{ id: LibraryCategory; label: string; icon: any }> = [
  { id: "all", label: "All", icon: Layers },
  { id: "images", label: "Images", icon: ImageIcon },
  { id: "documents", label: "Documents", icon: FileText }
]

const typeOptions: Array<{ value: LibraryItemType | "all"; label: string }> = [
  { value: "all", label: "All Types" },
  { value: "image", label: "Image" },
  { value: "document", label: "Document" },
  { value: "spreadsheet", label: "Spreadsheets" },
  { value: "presentation", label: "Presentation" },
  { value: "folder", label: "Folder" },
  { value: "note", label: "Note" }
]

const sourceOptions: Array<{ value: LibraryItemSource | "all"; label: string }> = [
  { value: "all", label: "All Sources" },
  { value: "uploaded", label: "Uploaded" },
  { value: "generated", label: "Generated" }
]

const currentTypeLabel = computed(() => {
  const found = typeOptions.find((t) => t.value === props.fileType)
  return found ? found.label : "All Types"
})

const currentSourceLabel = computed(() => {
  const found = sourceOptions.find((s) => s.value === props.source)
  return found ? found.label : "All Sources"
})
</script>

<template>
  <!-- Toolbar Row: Component-based ADropdown Selects, 32px Height, 14px Icon Metrics -->
  <div class="flex flex-wrap items-center justify-between gap-3 bg-transparent px-4 py-2">
    <!-- Left Category Tabs: Segmented Pill Controls -->
    <div class="flex h-8 items-center gap-0.5 rounded-[12px] bg-mist/80 p-0.5">
      <button
        v-for="cat in categories"
        :key="cat.id"
        type="button"
        class="inline-flex h-7 items-center gap-1.5 rounded-[10px] px-3 text-xs transition-all"
        :class="
          category === cat.id
            ? 'bg-paper text-[#0F172A] shadow-2xs font-medium'
            : 'text-[#64748B] hover:text-[#0F172A]'
        "
        @click="emit('update:category', cat.id)"
      >
        <component
          :is="cat.icon"
          :size="14"
          :stroke-width="1.75"
          aria-hidden="true"
        />
        <span>{{ cat.label }}</span>
      </button>
    </div>

    <!-- Right Controls: ant-design-vue ADropdown Component Selectors + View Switcher -->
    <div class="flex flex-wrap items-center gap-2">
      <!-- Type Filter ADropdown Component -->
      <ADropdown placement="bottomRight" trigger="click">
        <button
          type="button"
          class="inline-flex h-8 items-center gap-1.5 rounded-[10px] bg-mist/70 px-2.5 text-xs font-medium text-[#0F172A] transition-colors hover:bg-mist focus:outline-none"
        >
          <Filter :size="14" :stroke-width="1.75" class="text-[#64748B]" />
          <span>{{ currentTypeLabel }}</span>
          <ChevronDown :size="14" :stroke-width="1.75" class="text-[#64748B]" />
        </button>

        <template #overlay>
          <AMenu :selected-keys="[fileType]">
            <AMenuItem
              v-for="opt in typeOptions"
              :key="opt.value"
              @click="emit('update:fileType', opt.value)"
            >
              <span class="text-xs">{{ opt.label }}</span>
            </AMenuItem>
          </AMenu>
        </template>
      </ADropdown>

      <!-- Source Filter ADropdown Component -->
      <ADropdown placement="bottomRight" trigger="click">
        <button
          type="button"
          class="inline-flex h-8 items-center gap-1.5 rounded-[10px] bg-mist/70 px-2.5 text-xs font-medium text-[#0F172A] transition-colors hover:bg-mist focus:outline-none"
        >
          <span>{{ currentSourceLabel }}</span>
          <ChevronDown :size="14" :stroke-width="1.75" class="text-[#64748B]" />
        </button>

        <template #overlay>
          <AMenu :selected-keys="[source]">
            <AMenuItem
              v-for="opt in sourceOptions"
              :key="opt.value"
              @click="emit('update:source', opt.value)"
            >
              <span class="text-xs">{{ opt.label }}</span>
            </AMenuItem>
          </AMenu>
        </template>
      </ADropdown>

      <!-- View Switcher (List / Grid) -->
      <div class="flex h-8 items-center gap-0.5 rounded-[12px] bg-mist/80 p-0.5">
        <ATooltip title="List view (Default)">
          <button
            type="button"
            class="grid h-7 w-7 place-items-center rounded-[10px] text-xs transition-all"
            :class="
              viewMode === 'list'
                ? 'bg-paper text-[#0F172A] shadow-2xs font-medium'
                : 'text-[#64748B] hover:text-[#0F172A]'
            "
            aria-label="List view"
            @click="emit('update:viewMode', 'list')"
          >
            <LayoutList :size="14" :stroke-width="1.75" aria-hidden="true" />
          </button>
        </ATooltip>

        <ATooltip title="Grid view">
          <button
            type="button"
            class="grid h-7 w-7 place-items-center rounded-[10px] text-xs transition-all"
            :class="
              viewMode === 'grid'
                ? 'bg-paper text-[#0F172A] shadow-2xs font-medium'
                : 'text-[#64748B] hover:text-[#0F172A]'
            "
            aria-label="Grid view"
            @click="emit('update:viewMode', 'grid')"
          >
            <Grid :size="14" :stroke-width="1.75" aria-hidden="true" />
          </button>
        </ATooltip>
      </div>
    </div>
  </div>
</template>
