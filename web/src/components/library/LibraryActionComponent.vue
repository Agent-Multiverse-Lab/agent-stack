<script setup lang="ts">
import { Copy, Download, MoreHorizontal, Trash2 } from "@lucide/vue"
import { Dropdown as ADropdown, Menu as AMenu, MenuItem as AMenuItem, message } from "ant-design-vue"
import type { LibraryItem } from "@/types/library"

const props = defineProps<{
  item: LibraryItem
}>()

const emit = defineEmits<{
  (e: "download", item: LibraryItem): void
  (e: "delete", id: string): void
}>()

const handleCopyLink = () => {
  message.success(`Copied link for ${props.item.name}`)
}
</script>

<template>
  <!-- LibraryActionComponent: Standard Library Row Action Component -->
  <ADropdown placement="bottomRight" trigger="click">
    <button
      type="button"
      class="grid h-7 w-7 place-items-center rounded-md text-[#64748B] hover:bg-mist hover:text-[#0F172A] transition-colors"
      title="Actions"
      aria-label="Item actions"
    >
      <MoreHorizontal :size="16" :stroke-width="1.8" />
    </button>
    <template #overlay>
      <AMenu>
        <AMenuItem key="download" @click="emit('download', props.item)">
          <div class="flex items-center gap-2 px-1 py-0.5 text-xs text-[#0F172A]">
            <Download :size="13" class="text-[#64748B]" />
            <span>Download</span>
          </div>
        </AMenuItem>
        <AMenuItem key="copy" @click="handleCopyLink">
          <div class="flex items-center gap-2 px-1 py-0.5 text-xs text-[#0F172A]">
            <Copy :size="13" class="text-[#64748B]" />
            <span>Copy link</span>
          </div>
        </AMenuItem>
        <AMenuItem key="delete" danger @click="emit('delete', props.item.id)">
          <div class="flex items-center gap-2 px-1 py-0.5 text-xs">
            <Trash2 :size="13" />
            <span>Delete</span>
          </div>
        </AMenuItem>
      </AMenu>
    </template>
  </ADropdown>
</template>
