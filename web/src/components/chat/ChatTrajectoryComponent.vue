<script setup lang="ts">
import { Activity, CheckCircle2, Clock } from "@lucide/vue"

defineProps<{
  runId?: string
  status?: string
}>()
</script>

<template>
  <div class="flex flex-col gap-6 text-graphite">
    <div class="flex items-center gap-3">
      <div class="grid size-10 shrink-0 place-items-center rounded-xl bg-graphite/6 text-slate">
        <Activity :size="20" :stroke-width="1.8" />
      </div>
      <div class="min-w-0 flex-1">
        <h3 class="truncate text-sm font-medium">Agent Trajectory</h3>
        <p class="truncate text-xs text-slate">
          ID: {{ runId || "N/A" }}
        </p>
      </div>
    </div>

    <div class="rounded-xl border border-graphite/10 bg-graphite/[0.02] p-3 text-xs text-slate">
      <div class="flex items-center justify-between">
        <span>Execution Status</span>
        <span class="font-medium capitalize text-graphite">{{ status || "Running" }}</span>
      </div>
    </div>

    <div class="relative pl-4">
      <div class="absolute top-2 bottom-2 left-[19px] w-px bg-graphite/12" aria-hidden="true" />

      <div class="relative mb-6 flex gap-4">
        <div class="relative z-10 grid size-6 shrink-0 place-items-center rounded-full bg-paper text-emerald-600">
          <CheckCircle2 :size="18" :stroke-width="2" />
        </div>
        <div class="flex flex-col gap-0.5 pt-0.5">
          <span class="text-sm font-medium">Initialize Agent</span>
          <span class="text-xs text-slate">Ready for execution</span>
        </div>
      </div>

      <div class="relative flex gap-4">
        <div class="relative z-10 grid size-6 shrink-0 place-items-center rounded-full bg-paper text-blue-600">
          <Clock :size="16" :stroke-width="2" class="animate-spin" />
        </div>
        <div class="flex flex-col gap-0.5 pt-0.5">
          <span class="text-sm font-medium">Processing Pipeline</span>
          <span class="text-xs text-slate">Generating response...</span>
        </div>
      </div>
    </div>
  </div>
</template>
