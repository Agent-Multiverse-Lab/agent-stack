<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue"
import { ArrowUp, Plus } from "@lucide/vue"

import type { LocalAttachment } from "@/types/conversation"

import AttachmentComponent from "./AttachmentComponent.vue"

const props = defineProps<{
  draft: string
  attachments: LocalAttachment[]
}>()

const emit = defineEmits<{
  "update:draft": [value: string]
  submit: []
  "files-selected": [files: File[]]
  "remove-attachment": [id: string]
}>()

const textareaElement = ref<HTMLTextAreaElement | null>(null)
const measurementTextareaElement = ref<HTMLTextAreaElement | null>(null)
const controlsElement = ref<HTMLDivElement | null>(null)
const fileInputElement = ref<HTMLInputElement | null>(null)
const stackActions = ref(false)

let controlsResizeObserver: ResizeObserver | null = null
let controlsWidth = 0

const draftModel = computed({
  get: () => props.draft,
  set: (value: string) => emit("update:draft", value),
})

const canSubmit = computed(
  () => props.draft.trim().length > 0 || props.attachments.length > 0,
)

function setTextareaHeight(element: HTMLTextAreaElement) {
  element.style.height = "auto"
  element.style.height = `${Math.min(element.scrollHeight, 180)}px`
}

function shouldStackActions(value: string): boolean {
  const measurementElement = measurementTextareaElement.value

  if (!value || !measurementElement) {
    return false
  }

  measurementElement.value = value

  const styles = window.getComputedStyle(measurementElement)
  const lineHeight = Number.parseFloat(styles.lineHeight)
  const paddingTop = Number.parseFloat(styles.paddingTop)
  const paddingBottom = Number.parseFloat(styles.paddingBottom)
  const singleLineHeight = lineHeight + paddingTop + paddingBottom

  return measurementElement.scrollHeight > Math.ceil(singleLineHeight) + 1
}

function resizeTextarea(element = textareaElement.value) {
  if (!element) {
    return
  }

  setTextareaHeight(element)

  const nextStackActions = shouldStackActions(element.value)

  if (stackActions.value !== nextStackActions) {
    stackActions.value = nextStackActions
    void nextTick(() => setTextareaHeight(element))
  }
}

function handleInput(event: Event) {
  resizeTextarea(event.target as HTMLTextAreaElement)
}

function submitDraft() {
  if (canSubmit.value) {
    emit("submit")
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    submitDraft()
  }
}

function openFilePicker() {
  fileInputElement.value?.click()
}

function handleFileSelection(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])

  if (files.length) {
    emit("files-selected", files)
  }

  input.value = ""
}

watch(
  () => props.draft,
  async () => {
    await nextTick()
    resizeTextarea()
  },
)

onMounted(async () => {
  await nextTick()
  resizeTextarea()

  if (!controlsElement.value || typeof ResizeObserver === "undefined") {
    return
  }

  controlsWidth = controlsElement.value.clientWidth
  controlsResizeObserver = new ResizeObserver(([entry]) => {
    const nextWidth = entry?.contentRect.width ?? 0

    if (Math.abs(nextWidth - controlsWidth) < 1) {
      return
    }

    controlsWidth = nextWidth
    resizeTextarea()
  })
  controlsResizeObserver.observe(controlsElement.value)
})

onBeforeUnmount(() => {
  controlsResizeObserver?.disconnect()
})
</script>

<template>
  <form
    class="message-input"
    @submit.prevent="submitDraft"
  >
    <ul
      v-if="props.attachments.length"
      class="message-input-attachment-region"
      aria-label="Attachments"
    >
      <AttachmentComponent
        v-for="attachment in props.attachments"
        :key="attachment.id"
        :attachment="attachment"
        @remove="emit('remove-attachment', $event)"
      />
    </ul>

    <div
      ref="controlsElement"
      class="message-input-controls"
      :class="{ 'is-stacked': stackActions }"
    >
      <button
        class="message-input-file-button"
        type="button"
        aria-label="Add files"
        title="Add files"
        @click="openFilePicker"
      >
        <Plus
          class="message-input-file-icon"
          :size="20"
          :stroke-width="1.8"
          aria-hidden="true"
        />
      </button>

      <input
        ref="fileInputElement"
        class="message-input-file-control"
        type="file"
        multiple
        tabindex="-1"
        @change="handleFileSelection"
      >

      <label class="message-input-label">
        <span class="message-input-label-text">Type a message</span>
        <textarea
          ref="textareaElement"
          v-model="draftModel"
          class="message-input-textarea"
          rows="1"
          placeholder="Ask anything"
          aria-label="Type a message"
          @input="handleInput"
          @keydown="handleKeydown"
        />
      </label>

      <textarea
        ref="measurementTextareaElement"
        class="message-input-measurement"
        rows="1"
        tabindex="-1"
        aria-hidden="true"
        readonly
      />

      <button
        class="message-input-submit"
        :class="{ 'is-ready': canSubmit }"
        type="submit"
        :disabled="!canSubmit"
        aria-label="Send message"
        title="Send message"
      >
        <ArrowUp
          class="message-input-submit-icon"
          :size="18"
          :stroke-width="2"
          aria-hidden="true"
        />
      </button>
    </div>
  </form>
</template>

<style scoped>
@reference "../styles/index.css";

.message-input {
  @apply grid w-full border p-0;

  border-color: var(--color-border);
  border-radius: var(--radius-composer);
  background: var(--color-surface-muted);
}

.message-input-attachment-region {
  @apply m-0 flex min-w-0 list-none overflow-x-auto overflow-y-hidden;

  width: 100%;
  height: 64px;
  gap: 0.5rem;
  padding: 0.35rem 0.65rem 0.375rem;
  scrollbar-width: thin;
  scrollbar-color: var(--color-scrollbar-thumb) transparent;
}

.message-input-controls {
  @apply relative grid min-w-0 items-end py-[0.35rem] pr-2 pl-3;

  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 0.4rem;
}

.message-input-controls.is-stacked {
  grid-template-columns: minmax(0, 1fr) auto;
  row-gap: 0.1rem;
}

.message-input-controls.is-stacked .message-input-file-button {
  grid-column: 1;
  grid-row: 2;
  justify-self: start;
}

.message-input-controls.is-stacked .message-input-label {
  grid-column: 1 / -1;
  grid-row: 1;
}

.message-input-controls.is-stacked .message-input-submit {
  grid-column: 2;
  grid-row: 2;
}

.message-input-file-button,
.message-input-submit {
  @apply grid size-[34px] shrink-0 place-items-center bg-transparent;

  border-radius: var(--radius-pill);
}

.message-input-file-button {
  grid-column: 1;
  grid-row: 1;
  color: var(--color-text-muted);
}

.message-input-file-button:hover {
  color: var(--color-text);
  background: var(--color-surface-emphasis);
}

.message-input-file-icon,
.message-input-submit-icon {
  @apply shrink-0;
}

.message-input-file-control {
  @apply fixed h-px w-px overflow-hidden whitespace-nowrap;

  clip: rect(0 0 0 0);
  clip-path: inset(50%);
}

.message-input-file-control:focus-visible,
.message-input-textarea:focus-visible {
  outline: none;
}

.message-input-label {
  @apply block min-w-0;

  grid-column: 2;
  grid-row: 1;
}

.message-input-label-text {
  @apply absolute h-px w-px overflow-hidden whitespace-nowrap;

  clip: rect(0 0 0 0);
  clip-path: inset(50%);
}

.message-input-textarea,
.message-input-measurement {
  @apply block min-h-[38px] max-h-[180px] w-full resize-none border-0 bg-transparent px-1 outline-0;

  padding-block: 0.45rem;
  color: var(--color-text);
  font-family: var(--font-body);
  font-size: 0.95rem;
  line-height: 1.5;
}

.message-input-measurement {
  @apply pointer-events-none invisible absolute h-0 min-h-0 overflow-hidden;

  top: 0;
  right: calc(0.5rem + 34px + 0.4rem);
  left: calc(0.75rem + 34px + 0.4rem);
  width: auto;
}

.message-input-textarea::placeholder {
  color: var(--color-text-subtle);
}

.message-input-submit {
  @apply cursor-not-allowed;

  grid-column: 3;
  grid-row: 1;
  color: var(--color-text);
  opacity: 0.22;
  transition:
    background-color 120ms ease,
    color 120ms ease,
    opacity 120ms ease;
}

.message-input-submit.is-ready {
  @apply cursor-pointer opacity-100;

  color: var(--color-on-action);
  background: var(--color-action-primary);
}

.message-input-submit.is-ready:hover {
  background: var(--color-action-primary-hover);
}

@media (max-width: 560px) {
  .message-input-textarea,
  .message-input-measurement {
    font-size: 0.92rem;
  }
}
</style>
