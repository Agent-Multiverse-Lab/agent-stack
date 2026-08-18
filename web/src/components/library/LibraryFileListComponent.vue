<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue"
import {
  FileCode,
  FileText,
  Folder,
  Image as ImageIcon,
  Presentation,
  Sparkles,
  StickyNote,
  Table,
  UploadCloud
} from "@lucide/vue"
import LibraryActionComponent from "@/components/library/LibraryActionComponent.vue"
import type { LibraryItem, LibraryViewMode } from "@/types/library"

const props = defineProps<{
  items: LibraryItem[]
  viewMode: LibraryViewMode
  hasMore: boolean
  isLoadingMore: boolean
}>()

const emit = defineEmits<{
  (e: "load-more"): void
  (e: "delete-item", id: string): void
  (e: "download-item", item: LibraryItem): void
}>()

const sentinelRef = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

const setupObserver = () => {
  if (observer) observer.disconnect()

  observer = new IntersectionObserver(
    (entries) => {
      const target = entries[0]
      if (target.isIntersecting && props.hasMore && !props.isLoadingMore) {
        emit("load-more")
      }
    },
    { root: null, rootMargin: "200px", threshold: 0.1 }
  )

  if (sentinelRef.value) {
    observer.observe(sentinelRef.value)
  }
}

onMounted(() => {
  setupObserver()
})

onBeforeUnmount(() => {
  if (observer) observer.disconnect()
})

watch(
  () => [props.items.length, props.hasMore],
  () => {
    if (sentinelRef.value && observer) {
      observer.disconnect()
      if (props.hasMore) {
        observer.observe(sentinelRef.value)
      }
    }
  }
)

function formatBytes(bytes: number): string {
  if (bytes === 0) return "--"
  const k = 1024
  const sizes = ["B", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

function getItemIcon(type: LibraryItem["type"]) {
  switch (type) {
    case "image":
      return ImageIcon
    case "document":
      return FileText
    case "spreadsheet":
      return Table
    case "presentation":
      return Presentation
    case "folder":
      return Folder
    case "note":
      return StickyNote
    default:
      return FileCode
  }
}
</script>

<template>
  <div class="flex flex-1 flex-col overflow-y-auto px-4 py-4">
    <!-- Empty State -->
    <div
      v-if="items.length === 0"
      class="my-auto flex flex-col items-center justify-center py-16 text-center"
    >
      <div class="mb-3 grid h-12 w-12 place-items-center rounded-full bg-mist text-slate/60">
        <Folder :size="24" :stroke-width="1.5" aria-hidden="true" />
      </div>
      <h3 class="m-0 text-sm font-medium text-graphite">No items found</h3>
      <p class="m-0 mt-1 text-xs text-slate max-w-xs">
        No files, notes, or folders match your search or filter criteria.
      </p>
    </div>

    <!-- List View: Precise Typography & All Headers Left-Aligned -->
    <div v-else-if="viewMode === 'list'" class="w-full">
      <table class="w-full text-left text-xs text-graphite border-collapse">
        <thead>
          <!-- 表头: 全部左对齐 (text-left) -->
          <tr class="text-xs font-medium text-[#94A3B8] uppercase tracking-wider">
            <th class="pb-3 pt-1 pl-2 pr-4 font-medium text-left">NAME</th>
            <th class="pb-3 pt-1 px-4 font-medium text-left">MODIFIED</th>
            <th class="pb-3 pt-1 px-4 font-medium text-left">SIZE</th>
            <th class="pb-3 pt-1 pr-2 pl-4 text-right w-16"></th>
          </tr>
        </thead>
        <tbody>
          <!-- 表格行高 py-3, 44-48px 高度 -->
          <tr
            v-for="item in items"
            :key="item.id"
            class="group transition-colors h-[46px]"
          >
            <!-- 1. NAME (Primary Text, icon gap 12px) -->
            <td class="py-3 pl-2 pr-4 align-middle">
              <div class="flex items-center gap-3">
                <component
                  :is="getItemIcon(item.type)"
                  :size="18"
                  :stroke-width="1.8"
                  class="text-[#64748B] group-hover:text-[#0F172A] transition-colors shrink-0"
                />
                <span
                  class="truncate text-sm font-medium text-[#0F172A] transition-all"
                  :title="item.name"
                >
                  {{ item.name }}
                </span>
              </div>
            </td>

            <!-- 2. MODIFIED -->
            <td class="py-3 px-4 align-middle text-[13px] text-[#64748B]">
              {{ item.createdAt || item.updatedAt }}
            </td>

            <!-- 3. SIZE (Left-Aligned text-left) -->
            <td class="py-3 px-4 align-middle text-left font-mono text-[13px] text-[#64748B]">
              {{ formatBytes(item.sizeBytes) }}
            </td>

            <!-- 4. ACTIONS (Single LibraryActionComponent, Hover-only) -->
            <td class="py-3 pr-2 pl-4 align-middle text-right">
              <div class="flex items-center justify-end opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto transition-opacity duration-150">
                <LibraryActionComponent
                  :item="item"
                  @download="emit('download-item', $event)"
                  @delete="emit('delete-item', $event)"
                />
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Grid View -->
    <div
      v-else
      class="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-5 py-2"
    >
      <div
        v-for="item in items"
        :key="item.id"
        class="group relative flex flex-col justify-between p-2"
      >
        <!-- Top Preview / Icon Box -->
        <div class="relative mb-2.5 flex h-26 w-full items-center justify-center overflow-hidden rounded-xl bg-mist/50">
          <img
            v-if="item.type === 'image' && item.thumbnailUrl"
            :src="item.thumbnailUrl"
            :alt="item.name"
            class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
          >
          <component
            :is="getItemIcon(item.type)"
            v-else
            :size="32"
            :stroke-width="1.4"
            class="text-[#64748B] transition-transform group-hover:scale-105"
            aria-hidden="true"
          />

          <!-- Source Badge -->
          <div class="absolute top-2 left-2 flex items-center gap-1 text-[10px] font-medium text-slate">
            <Sparkles v-if="item.source === 'generated'" :size="9" class="text-emerald-600" />
            <UploadCloud v-else :size="9" />
            <span class="capitalize">{{ item.source }}</span>
          </div>

          <!-- Actions (Single LibraryActionComponent, Hover-only) -->
          <div class="absolute top-2 right-2 opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto transition-opacity duration-150">
            <LibraryActionComponent
              :item="item"
              @download="emit('download-item', $event)"
              @delete="emit('delete-item', $event)"
            />
          </div>
        </div>

        <!-- Details -->
        <div>
          <h4 class="m-0 truncate text-sm font-medium text-[#0F172A] transition-all" :title="item.name">
            {{ item.name }}
          </h4>
          <div class="mt-1.5 flex items-center justify-between text-[13px] text-[#64748B]">
            <span>{{ item.createdAt || item.updatedAt }}</span>
            <span>{{ formatBytes(item.sizeBytes) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Sentinel & Loading for Infinite Scroll -->
    <div
      ref="sentinelRef"
      class="mt-6 flex flex-col items-center justify-center py-4 text-xs text-[#64748B]"
    >
      <div v-if="isLoadingMore" class="flex items-center gap-2">
        <span class="h-3.5 w-3.5 animate-spin rounded-full border-2 border-graphite/20 border-t-graphite" />
        <span>Loading more items...</span>
      </div>
      <p v-else-if="!hasMore && items.length > 0" class="m-0 text-[11px] text-[#94A3B8]">
        All items loaded (Max 10 per page)
      </p>
    </div>
  </div>
</template>
