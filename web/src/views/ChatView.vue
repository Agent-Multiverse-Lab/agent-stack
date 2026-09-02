<script setup lang="ts">
import { computed, onBeforeUnmount, watch, nextTick, ref } from "vue";
import { storeToRefs } from "pinia";
import { ArrowDown } from "@lucide/vue";
import { useRouter } from "vue-router";

import {
  createThread,
  getThreadDetail,
  listChatAgents,
  uploadChatAttachments,
} from "@/api/agent";
import ChatLoadingStateComponent from "@/components/chat/loading/ChatLoadingStateComponent.vue";
import ChatMessageComponent from "@/components/chat/ChatMessageComponent.vue";
import ChatMessageInputComponent from "@/components/chat/ChatMessageInputComponent.vue";
import ChatThinkingGroupComponent from "@/components/chat/loading/ChatThinkingGroupComponent.vue";
import ChatAskUserComponent from "@/components/chat/hil/ChatAskUserComponent.vue";
import { useAgentRun } from "@/composables/useAgentRun";
import { useChat } from "@/composables/useChat";
import { useModelStore } from "@/stores/useModelStore";
import type { AgentRunEndEvent, ChatMessage } from "@/types/chat";

const props = defineProps<{
  threadId?: string;
}>();

const messageScroller = ref<HTMLElement | null>(null);
const showScrollToBottom = ref(false);

const scrollToBottom = async (behavior: "auto" | "smooth" = "auto") => {
  await nextTick();
  const element = messageScroller.value;
  if (!element) return;
  element.scrollTo({
    top: element.scrollHeight,
    behavior,
  });
  showScrollToBottom.value = false;
};

const updateScrollButton = () => {
  const element = messageScroller.value;
  if (!element) return;
  const distanceToBottom =
    element.scrollHeight - element.scrollTop - element.clientHeight;
  showScrollToBottom.value = distanceToBottom > 48;
};

const router = useRouter();
const modelStore = useModelStore();
const {
  models,
  selectedModelId,
  loading: modelsLoading,
} = storeToRefs(modelStore);

const {
  runId,
  runStatus,
  streamUrl,
  pendingInteraction,
  cancelling,
  resuming,
  isRunActive,
  createRun,
  resumeRun,
  restoreRunFromThread,
  consumeRunStream,
  cancelCurrentRun: requestRunCancellation,
  clearRun,
} = useAgentRun();
const {
  thread,
  messages,
  draft,
  attachments,
  uploadingCount,
  uploadError,
  loading,
  submitting,
  error,
  clearPendingInput,
  applyThreadDetail,
  applyCreatedThread,
  clearRunStreamMessages,
  applyRunMessageEvent,
  beginSubmission,
  rollbackSubmission,
  appendUploadedAttachments,
  resetThread,
  removeAttachment,
} = useChat();

let streamController: AbortController | null = null;
let operation = 0;
let uploadGeneration = 0;

const errorText = (caught: unknown) =>
  caught instanceof Error ? caught.message : "请求失败";

const isAbortError = (caught: unknown) =>
  caught instanceof DOMException && caught.name === "AbortError";

const abortStream = () => {
  streamController?.abort();
  streamController = null;
};

const loadAndApplyThread = async (
  threadId: string,
  expectedOperation: number,
) => {
  const detail = await getThreadDetail(threadId);
  if (operation !== expectedOperation) return null;
  applyThreadDetail(detail);
  return restoreRunFromThread(detail);
};

const monitorRun = async (threadId: string, expectedOperation: number) => {
  const monitoredRunId = runId.value;
  if (!monitoredRunId || !streamUrl.value || !isRunActive.value) return;

  while (
    operation === expectedOperation &&
    runId.value === monitoredRunId &&
    streamUrl.value &&
    isRunActive.value
  ) {
    clearRunStreamMessages(monitoredRunId);
    const controller = new AbortController();
    streamController = controller;
    let endEvent: AgentRunEndEvent;
    try {
      const consumedEndEvent = await consumeRunStream(
        controller.signal,
        (event) => {
          if (
            operation === expectedOperation &&
            runId.value === monitoredRunId
          ) {
            applyRunMessageEvent(event, monitoredRunId);
          }
        },
      );
      if (!consumedEndEvent) return;
      endEvent = consumedEndEvent;
    } catch (caught) {
      if (operation !== expectedOperation || isAbortError(caught)) return;
      error.value = errorText(caught);
      try {
        await loadAndApplyThread(threadId, expectedOperation);
      } catch {
        // 保持已知 Run 状态，稍后重新连接。
      }
      if (operation !== expectedOperation || runId.value !== monitoredRunId) {
        return;
      }
      if (!isRunActive.value) {
        error.value = runStatus.value === "failed" ? "Agent 执行失败" : "";
        return;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
      continue;
    } finally {
      if (streamController === controller) streamController = null;
    }

    if (operation !== expectedOperation) return;
    error.value = "";
    try {
      await loadAndApplyThread(threadId, expectedOperation);
    } catch (caught) {
      if (operation === expectedOperation && !isAbortError(caught)) {
        error.value = errorText(caught);
      }
    }
    if (operation !== expectedOperation) return;
    if (endEvent.status === "failed") {
      error.value = endEvent.error || "Agent 执行失败";
    }
    return;
  }
};

const loadThread = async (threadId: string) => {
  const expectedOperation = ++operation;
  uploadGeneration += 1;
  abortStream();
  clearRun();
  clearPendingInput();
  submitting.value = false;
  thread.value = null;
  messages.value = [];
  loading.value = true;
  error.value = "";
  try {
    const activeRun = await loadAndApplyThread(threadId, expectedOperation);
    if (activeRun && isRunActive.value) {
      void monitorRun(threadId, expectedOperation);
    }
  } catch (caught) {
    if (operation === expectedOperation && !isAbortError(caught)) {
      thread.value = null;
      messages.value = [];
      error.value = errorText(caught);
    }
  } finally {
    if (operation === expectedOperation) loading.value = false;
  }
};

const uploadFiles = async (files: File[]) => {
  if (files.length === 0) return;

  const expectedGeneration = uploadGeneration;
  uploadingCount.value += files.length;
  uploadError.value = "";
  try {
    const uploaded = await uploadChatAttachments(files);
    if (uploadGeneration !== expectedGeneration) return;
    appendUploadedAttachments(uploaded);
  } catch (caught) {
    if (uploadGeneration === expectedGeneration) {
      uploadError.value = errorText(caught);
    }
  } finally {
    if (uploadGeneration === expectedGeneration) {
      uploadingCount.value = Math.max(0, uploadingCount.value - files.length);
    }
  }
};

const submit = async () => {
  if (isRunActive.value || pendingInteraction.value) return;
  const submission = beginSubmission();
  if (!submission) return;

  const expectedOperation = ++operation;
  abortStream();
  let runCreated = false;
  try {
    let currentThread = thread.value;

    if (!currentThread) {
      const agents = await listChatAgents();
      const leader = agents.find((agent) => agent.id === "LeaderAgent");
      if (!leader) throw new Error("LeaderAgent 当前不可用");

      const created = await createThread(leader.id);
      if (operation !== expectedOperation) return;
      currentThread = applyCreatedThread(created);
      if (props.threadId !== created.thread_id) {
        await router.replace({
          name: "conversation",
          params: { threadId: created.thread_id },
        });
      }
    }

    if (operation !== expectedOperation) return;
    const run = await createRun({
      query: submission.query,
      agentId: currentThread.agent_id,
      threadId: currentThread.thread_id,
      attachmentFileIds: submission.attachments.map(
        (attachment) => attachment.file_id,
      ),
      modelId: selectedModelId.value || undefined,
    });
    if (operation !== expectedOperation) return;
    runCreated = true;

    try {
      await loadAndApplyThread(currentThread.thread_id, expectedOperation);
    } catch (caught) {
      if (operation === expectedOperation && !isAbortError(caught)) {
        error.value = errorText(caught);
      }
    }
    if (operation !== expectedOperation) return;
    if (run.status === "failed") error.value = "Agent 执行失败";

    await monitorRun(currentThread.thread_id, expectedOperation);
  } catch (caught) {
    if (operation === expectedOperation && !isAbortError(caught)) {
      error.value = errorText(caught);
      if (!runCreated) rollbackSubmission(submission);
    }
  } finally {
    if (operation === expectedOperation) {
      streamController = null;
      submitting.value = false;
    }
  }
};

const cancelCurrentRun = async () => {
  error.value = "";
  try {
    await requestRunCancellation();
  } catch (caught) {
    error.value = errorText(caught);
  }
};

// FIXEME: 回答提交后立即切换到后端返回的新 Resume Run Stream。
const submitResume = async (answer: string) => {
  const interaction = pendingInteraction.value;
  const currentThread = thread.value;
  if (!interaction || !currentThread || resuming.value) return;

  const expectedOperation = ++operation;
  abortStream();
  error.value = "";
  try {
    await resumeRun(interaction.parent_run_id, {
      thread_id: currentThread.thread_id,
      thread_metadata: {
        request_id: crypto.randomUUID(),
        resume: { answer },
      },
    });
    if (operation !== expectedOperation) return;
    await monitorRun(currentThread.thread_id, expectedOperation);
  } catch (caught) {
    if (operation === expectedOperation && !isAbortError(caught)) {
      error.value = errorText(caught);
    }
  }
};

const stop = () => {
  operation += 1;
  uploadGeneration += 1;
  abortStream();
  clearRun();
};

const inputDisabled = computed(
  () =>
    loading.value ||
    cancelling.value ||
    resuming.value ||
    Boolean(pendingInteraction.value) ||
    (submitting.value && !isRunActive.value),
);
const composerDocked = computed(() => messages.value.length > 0);
const displayedError = computed(() => uploadError.value || error.value);

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const hasCurrentRunAssistantText = computed(() => {
  const currentRunId = runId.value;
  if (!currentRunId) return false;

  return messages.value.some((message) => {
    if (message.type !== "ai" || message.payload.type !== "text") return false;
    const event = isRecord(message.payload.event)
      ? message.payload.event
      : null;
    return (
      event?.run_id === currentRunId &&
      typeof event.content === "string" &&
      event.content.trim().length > 0
    );
  });
});

const messageKey = (message: ChatMessage, index: number) => {
  const event = isRecord(message.payload.event) ? message.payload.event : null;
  const eventId = event?.message_id ?? event?.id;
  return typeof eventId === "string" || typeof eventId === "number"
    ? `${message.type}:${message.payload.type}:${eventId}`
    : `${message.type}:${message.payload.type}:${index}`;
};

watch(messages, () => void scrollToBottom());

watch(
  () => props.threadId,
  (threadId) => {
    if (!threadId) {
      stop();
      resetThread();
      return;
    }
    if (thread.value?.thread_id !== threadId) void loadThread(threadId);
  },
  { immediate: true },
);

onBeforeUnmount(stop);
</script>

<template>
  <section class="relative flex h-full min-h-0 flex-col bg-paper text-graphite">
    <div
      ref="messageScroller"
      class="min-h-0 flex-1 overflow-y-auto overscroll-contain"
      @scroll.passive="updateScrollButton"
    >
      <div
        class="mx-auto grid w-full max-w-[52rem] content-start gap-7 px-[clamp(1rem,4vw,2rem)] pt-6 pb-10"
      >
        <ChatLoadingStateComponent
          v-if="loading"
          label="Loading conversation"
        />

        <template v-else>
          <ChatMessageComponent
            v-for="(message, index) in messages"
            :key="messageKey(message, index)"
            :message="message"
          />
        </template>

        <ChatAskUserComponent
          v-if="!loading && pendingInteraction"
          :interaction="pendingInteraction"
          :disabled="resuming"
          @submit="submitResume"
        />

        <Transition
          enter-active-class="transition-opacity duration-200 ease-out motion-reduce:transition-none"
          leave-active-class="transition-opacity duration-150 ease-in motion-reduce:transition-none"
          enter-from-class="opacity-0"
          leave-to-class="opacity-0"
        >
          <ChatThinkingGroupComponent
            v-if="!loading && isRunActive && !hasCurrentRunAssistantText"
            :key="runId ?? 'pending'"
          />
        </Transition>
      </div>
    </div>

    <footer
      class="inset-x-0 px-[clamp(0.75rem,4vw,2rem)]"
      :class="
        composerDocked
          ? 'shrink-0 bg-paper pt-2 pb-[max(1rem,env(safe-area-inset-bottom))]'
          : 'absolute top-[38%] -translate-y-1/2'
      "
    >
      <div class="relative mx-auto grid w-full max-w-[48rem] gap-2">
        <div
          v-if="!composerDocked && !loading"
          class="mb-4 text-center select-none"
        >
          <h1
            class="text-3xl font-semibold tracking-tight text-graphite sm:text-4xl"
          >
            Welcome to AM
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

        <button
          v-if="composerDocked && showScrollToBottom"
          type="button"
          class="absolute left-1/2 top-0 z-10 grid size-9 -translate-x-1/2 -translate-y-[calc(100%+0.75rem)] place-items-center rounded-full border border-graphite/10 bg-paper text-slate shadow-sm transition-colors hover:bg-mist hover:text-graphite focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-graphite/35"
          aria-label="Scroll to latest message"
          title="Scroll to latest message"
          @click="scrollToBottom('smooth')"
        >
          <ArrowDown :size="17" :stroke-width="2" aria-hidden="true" />
        </button>

        <ChatMessageInputComponent
          v-model="draft"
          :attachments="attachments"
          :uploading="uploadingCount"
          :running="isRunActive"
          :disabled="inputDisabled"
          :action-menu-placement="composerDocked ? 'top' : 'bottom'"
          :models="models"
          :model-id="selectedModelId"
          :models-loading="modelsLoading"
          @update:model-id="modelStore.selectModel"
          @files-selected="uploadFiles"
          @remove-attachment="removeAttachment"
          @submit="submit"
          @cancel="cancelCurrentRun"
        />
      </div>
    </footer>
  </section>
</template>
