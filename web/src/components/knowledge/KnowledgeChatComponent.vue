<script setup lang="ts">
import { computed } from "vue"
import { Empty as AEmpty } from "ant-design-vue"
import { MessagesSquare } from "@lucide/vue"

import type { KnowledgeFileItem } from "@/types/knowledge"

import KnowledgeComposerComponent from "./KnowledgeComposerComponent.vue"

const props = defineProps<{
  files: KnowledgeFileItem[]
}>()

const chatEnabled = computed(() =>
  props.files.some((file) => file.status === "indexed")
)

const emptyStateCopy = computed(() =>
  props.files.length ? "No indexed files" : "Add a file to start"
)
</script>

<template>
  <section
    id="knowledge-chat-region"
    class="grid h-full min-h-0 min-w-0 w-full overflow-hidden rounded-[16px] border border-graphite/10 bg-paper caret-transparent [grid-template-rows:48px_minmax(0,1fr)_auto] focus-visible:outline-offset-[-3px]"
    tabindex="-1"
    aria-labelledby="knowledge-chat-title"
  >
    <header class="flex h-12 min-w-0 items-center border-b border-graphite/6 px-4 select-none caret-transparent">
      <h1
        id="knowledge-chat-title"
        class="m-0 truncate text-base font-semibold tracking-[-0.03em] select-none caret-transparent cursor-default"
      >
        Knowledge Chat
      </h1>
    </header>

    <div class="min-h-0 overflow-y-auto overscroll-contain bg-mist">
      <AEmpty class="knowledge-chat-empty grid h-full place-content-center m-auto max-w-[25rem] min-h-[18rem] p-8">
        <template #image>
          <span class="grid h-[3.4rem] w-[3.4rem] place-items-center rounded-[16px] border border-graphite/16 bg-paper text-slate" aria-hidden="true">
            <MessagesSquare :size="28" :stroke-width="1.45" />
          </span>
        </template>
        <template #description>
          <strong class="text-graphite tracking-[-0.02em]">
            {{ emptyStateCopy }}
          </strong>
        </template>
      </AEmpty>
    </div>

    <KnowledgeComposerComponent
      :enabled="chatEnabled"
    />
  </section>
</template>
