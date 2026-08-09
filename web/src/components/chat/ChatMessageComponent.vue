<script setup lang="ts">
import MarkdownRender from "markstream-vue"

import AttachmentComponent from "@/components/AttachmentComponent.vue"
import type { ThreadMessageResponse } from "@/types/chat"

defineProps<{
  message: ThreadMessageResponse
}>()
</script>

<template>
  <article
    v-if="message.role === 'user'"
    class="flex justify-end"
  >
    <div
      class="max-w-[min(82%,42rem)] rounded-[1.15rem] bg-mist px-4 py-2.5 text-graphite"
    >
      <p
        v-if="message.content"
        class="m-0 whitespace-pre-wrap leading-7"
      >
        {{ message.content }}
      </p>

      <ul
        v-if="message.attachments.length"
        class="m-0 flex list-none flex-wrap gap-2 p-0"
        :class="{ 'mt-3': message.content }"
      >
        <AttachmentComponent
          v-for="attachment in message.attachments"
          :key="attachment.file_id"
          :attachment="attachment"
        />
      </ul>
    </div>
  </article>

  <article
    v-else-if="message.role === 'assistant'"
    class="min-w-0 max-w-full leading-7 text-graphite"
  >
    <MarkdownRender
      v-if="message.content"
      mode="chat"
      :content="message.content"
      :final="true"
    />

    <ul
      v-if="message.attachments.length"
      class="m-0 flex list-none flex-wrap gap-2 p-0"
      :class="{ 'mt-3': message.content }"
    >
      <AttachmentComponent
        v-for="attachment in message.attachments"
        :key="attachment.file_id"
        :attachment="attachment"
      />
    </ul>
  </article>

  <article v-else class="whitespace-pre-wrap text-sm text-slate">
    {{ message.content }}
  </article>
</template>
