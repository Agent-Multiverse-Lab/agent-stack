<script setup lang="ts">
import { computed } from "vue"
import MarkdownRender from "markstream-vue"

import AttachmentComponent from "@/components/AttachmentComponent.vue"
import AgentToolGroupComponent from "@/components/chat/tools/AgentToolGroupComponent.vue"
import type { ThreadMessageAttachmentResponse } from "@/types/attachment"
import type { ChatMessage } from "@/types/chat"

const props = defineProps<{
  message: ChatMessage
}>()

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null

const isAttachment = (
  value: unknown
): value is ThreadMessageAttachmentResponse =>
  isRecord(value) && typeof value.file_id === "string"

const event = computed(() =>
  isRecord(props.message.payload.event)
    ? props.message.payload.event
    : {}
)
const content = computed(() =>
  typeof event.value.content === "string" ? event.value.content : ""
)
const attachments = computed(() =>
  Array.isArray(event.value.attachments)
    ? event.value.attachments.filter(isAttachment)
    : []
)
const isAiText = computed(
  () => props.message.type === "ai" && props.message.payload.type === "text"
)
const isAiTool = computed(
  () => props.message.type === "ai" && props.message.payload.type === "tool"
)
const isFinal = computed(() => event.value.status !== "streaming")
</script>

<template>
  <article
    v-if="message.type === 'human'"
    class="flex justify-end"
  >
    <div
      class="max-w-[min(82%,42rem)] rounded-[1.15rem] bg-mist px-4 py-2.5 text-graphite"
    >
      <p
        v-if="content"
        class="m-0 whitespace-pre-wrap leading-7"
      >
        {{ content }}
      </p>

      <ul
        v-if="attachments.length"
        class="m-0 flex list-none flex-wrap gap-2 p-0"
        :class="{ 'mt-3': content }"
      >
        <AttachmentComponent
          v-for="attachment in attachments"
          :key="attachment.file_id"
          :attachment="attachment"
        />
      </ul>
    </div>
  </article>

  <article
    v-else-if="isAiText"
    class="min-w-0 max-w-full leading-7 text-graphite"
  >
    <MarkdownRender
      v-if="content"
      mode="chat"
      :content="content"
      :final="isFinal"
    />

    <ul
      v-if="attachments.length"
      class="m-0 flex list-none flex-wrap gap-2 p-0"
      :class="{ 'mt-3': content }"
    >
      <AttachmentComponent
        v-for="attachment in attachments"
        :key="attachment.file_id"
        :attachment="attachment"
      />
    </ul>
  </article>

  <AgentToolGroupComponent
    v-else-if="isAiTool"
    :event="event"
  />

  <article v-else class="whitespace-pre-wrap text-sm text-slate">
    {{ content }}
  </article>
</template>
