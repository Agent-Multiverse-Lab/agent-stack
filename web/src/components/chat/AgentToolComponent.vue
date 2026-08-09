<script setup lang="ts">
import { computed, ref } from "vue"
import {
  ChevronDown,
  CircleCheck,
  CircleX,
  LoaderCircle
} from "@lucide/vue"

import type { AgentTool } from "@/types/chat"

const props = defineProps<AgentTool>()

const expanded = ref(false)
const formattedState = computed(() => JSON.stringify(props.state, null, 2))
</script>

<template>
  <div
    class="agent-tool relative grid min-w-0 grid-cols-[2rem_minmax(0,1fr)_2rem] items-start gap-x-3 py-2"
  >
    <span
      class="relative z-10 grid size-8 place-items-center rounded-full bg-paper"
      :class="{
        'text-graphite': state.status === 'running',
        'text-slate': state.status === 'completed',
        'text-danger': state.status === 'failed'
      }"
      aria-hidden="true"
    >
      <LoaderCircle
        v-if="state.status === 'running'"
        class="motion-safe:animate-spin"
        :size="25"
        :stroke-width="1.8"
      />
      <CircleCheck
        v-else-if="state.status === 'completed'"
        :size="25"
        :stroke-width="1.7"
      />
      <CircleX
        v-else
        :size="25"
        :stroke-width="1.8"
      />
    </span>

    <div class="flex min-h-8 min-w-0 items-center gap-3 py-1">
      <strong
        class="min-w-0 truncate font-utility text-sm font-bold tracking-[0.04em]"
        :class="{ 'text-danger': state.status === 'failed' }"
      >
        {{ name }}
      </strong>
      <span class="text-graphite/30" aria-hidden="true">—</span>
      <span class="min-w-0 truncate font-utility text-sm text-slate">
        {{ state.status }}
      </span>
    </div>

    <button
      class="grid size-8 place-items-center rounded-full bg-transparent text-slate transition-colors duration-150 hover:bg-mist hover:text-graphite motion-reduce:transition-none"
      type="button"
      :aria-expanded="expanded"
      :aria-label="expanded ? `Collapse ${name} state` : `Expand ${name} state`"
      @click="expanded = !expanded"
    >
      <ChevronDown
        class="transition-transform duration-150 motion-reduce:transition-none"
        :class="{ 'rotate-180': expanded }"
        :size="18"
        :stroke-width="1.8"
        aria-hidden="true"
      />
    </button>

    <pre
      v-if="expanded"
      class="col-start-2 col-end-4 mt-2 min-w-0 overflow-x-auto rounded-md border border-graphite/8 bg-mist p-4 font-utility text-xs leading-6 text-graphite"
    >{{ formattedState }}</pre>
  </div>
</template>

<style scoped>
.agent-tool:has(+ .agent-tool)::after {
  position: absolute;
  top: 2.5rem;
  bottom: -0.5rem;
  left: calc(1rem - 0.5px);
  width: 1px;
  background: color-mix(in srgb, var(--color-graphite) 16%, transparent);
  content: "";
}
</style>
