<script setup lang="ts">
import { File as FileIcon, HardDrive, Tag } from "@lucide/vue"

defineProps<{
  fileId?: string
  fileName?: string
  contentType?: string
  fileSize?: number
  accessUrl?: string | null
}>()

const formatBytes = (bytes = 0) => {
  if (bytes === 0) return "0 B"
  const k = 1024
  const sizes = ["B", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
}
</script>

<template>
  <div class="flex flex-col gap-6 text-graphite">
    <div class="flex flex-col items-center gap-3 pt-2 pb-1 text-center">
      <div class="grid size-16 shrink-0 place-items-center rounded-2xl bg-graphite/6 text-slate">
        <FileIcon :size="32" :stroke-width="1.8" />
      </div>
      <div class="w-full">
        <h3 class="truncate text-base font-medium" :title="fileName">
          {{ fileName || "Attachment Document" }}
        </h3>
        <p class="mt-1 text-xs text-slate">
          {{ formatBytes(fileSize || 0) }}
        </p>
      </div>
    </div>

    <div class="rounded-xl border border-graphite/10 bg-graphite/[0.02] p-4">
      <h4 class="mb-3 text-xs font-semibold uppercase tracking-wider text-slate">
        Metadata & Source
      </h4>
      <dl class="flex flex-col gap-2.5 text-xs">
        <div class="flex items-center justify-between gap-3">
          <dt class="text-slate">File ID</dt>
          <dd class="truncate font-mono font-medium" :title="fileId">
            {{ fileId || "N/A" }}
          </dd>
        </div>

        <div class="flex items-center justify-between gap-3">
          <dt class="flex items-center gap-1.5 text-slate">
            <Tag :size="13" :stroke-width="1.8" />
            <span>MIME Type</span>
          </dt>
          <dd class="font-medium">
            {{ contentType || "application/octet-stream" }}
          </dd>
        </div>

        <div class="flex items-center justify-between gap-3">
          <dt class="flex items-center gap-1.5 text-slate">
            <HardDrive :size="13" :stroke-width="1.8" />
            <span>Source</span>
          </dt>
          <dd class="font-medium text-slate">
            Chat Attachment
          </dd>
        </div>
      </dl>
    </div>

    <div v-if="accessUrl" class="flex justify-center">
      <a
        :href="accessUrl"
        target="_blank"
        rel="noopener noreferrer"
        class="inline-flex items-center justify-center rounded-full bg-graphite px-4 py-2 text-xs font-medium text-paper transition-opacity hover:opacity-90"
      >
        View Original File
      </a>
    </div>
  </div>
</template>
