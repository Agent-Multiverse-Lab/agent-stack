<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from "vue"
import { useRouter } from "vue-router"

import ChatMessageComponent from "@/components/chat/ChatMessageComponent.vue"
import ChatMessageInputComponent from "@/components/chat/ChatMessageInputComponent.vue"
import { useChat } from "@/composables/useChat"

const props = defineProps<{
  threadId?: string
}>()

const router = useRouter()
const {
  thread,
  messages,
  draft,
  attachments,
  uploadingCount,
  uploadError,
  loading,
  submitting,
  cancelling,
  error,
  isRunActive,
  loadThread,
  resetThread,
  uploadFiles,
  removeAttachment,
  submitDraft,
  cancelCurrentRun,
  stop
} = useChat()

const inputDisabled = computed(
  () => loading.value || cancelling.value || (submitting.value && !isRunActive.value)
)
const composerDocked = computed(() => messages.value.length > 0)
const displayedError = computed(() => uploadError.value || error.value)

watch(
  () => props.threadId,
  (threadId) => {
    if (!threadId) {
      resetThread()
      return
    }
    if (thread.value?.thread_id !== threadId) void loadThread(threadId)
  },
  { immediate: true }
)

const submit = () =>
  submitDraft(async (threadId) => {
    if (props.threadId === threadId) return
    await router.replace({
      name: "conversation",
      params: { threadId }
    })
  })

onBeforeUnmount(stop)
</script>

<template>
  <section class="relative flex h-full min-h-0 flex-col bg-paper text-graphite">
    <div class="min-h-0 flex-1 overflow-y-auto overscroll-contain">
      <div
        class="mx-auto grid w-full max-w-[52rem] content-start gap-7 px-[clamp(1rem,4vw,2rem)] pt-6 pb-10"
      >
        <p v-if="loading" class="m-0 text-sm text-slate" role="status">
          Loading conversation…
        </p>

        <template v-else>
          <ChatMessageComponent
            v-for="message in messages"
            :key="message.message_id"
            :message="message"
          />
        </template>

        <Transition
          enter-active-class="transition-opacity duration-200 ease-out motion-reduce:transition-none"
          leave-active-class="transition-opacity duration-150 ease-in motion-reduce:transition-none"
          enter-from-class="opacity-0"
          leave-to-class="opacity-0"
        >
          <div
            v-if="isRunActive"
            class="flex items-center gap-4 py-1"
            role="status"
            aria-live="polite"
          >
            <span class="flex items-center gap-1.5" aria-hidden="true">
              <span class="size-1.5 animate-pulse rounded-full bg-slate [animation-delay:-0.3s] motion-reduce:animate-none" />
              <span class="size-1.5 animate-pulse rounded-full bg-slate [animation-delay:-0.15s] motion-reduce:animate-none" />
              <span class="size-1.5 animate-pulse rounded-full bg-slate motion-reduce:animate-none" />
            </span>
            <span
              class="animate-pulse bg-gradient-to-r from-violet-500 to-pink-500 bg-clip-text text-lg font-medium text-transparent motion-reduce:animate-none"
            >
              Thinking...
            </span>
          </div>
        </Transition>
      </div>
    </div>

    <footer
      class="inset-x-0 px-[clamp(0.75rem,4vw,2rem)]"
      :class="composerDocked
        ? 'shrink-0 bg-paper pt-2 pb-[max(1rem,env(safe-area-inset-bottom))]'
        : 'absolute top-[38%] -translate-y-1/2'"
    >
      <div class="mx-auto grid w-full max-w-[48rem] gap-2">
        <div
          v-if="!composerDocked && !loading"
          class="mb-4 text-center select-none"
        >
          <h1 class="text-3xl font-semibold tracking-tight text-graphite sm:text-4xl">
            Welcome to Multi-Agent S2C
          </h1>
          <p class="mt-2 text-sm text-slate sm:text-base">
            What would you like to explore or build today?
          </p>
        </div>

        <p
          v-if="displayedError"
          class="m-0 rounded-md bg-danger/6 px-3 py-2 text-sm text-danger"
          role="alert"
        >
          {{ displayedError }}
        </p>

        <ChatMessageInputComponent
          v-model="draft"
          :attachments="attachments"
          :uploading="uploadingCount"
          :running="isRunActive"
          :disabled="inputDisabled"
          :action-menu-placement="composerDocked ? 'top' : 'bottom'"
          @files-selected="uploadFiles"
          @remove-attachment="removeAttachment"
          @submit="submit"
          @cancel="cancelCurrentRun"
        />
      </div>
    </footer>
  </section>
</template>
