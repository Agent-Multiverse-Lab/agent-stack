<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch
} from "vue"
import { ArrowUp, Paperclip, Square } from "@lucide/vue"

import AttachmentComponent from "@/components/AttachmentComponent.vue"
import type { UploadedAttachmentResponse } from "@/types/attachment"

const props = defineProps<{
  modelValue: string
  attachments: UploadedAttachmentResponse[]
  uploading: number
  running: boolean
  disabled: boolean
}>()

const emit = defineEmits<{
  "update:modelValue": [value: string]
  "files-selected": [files: File[]]
  "remove-attachment": [fileId: string]
  submit: []
  cancel: []
}>()

const editor = ref<HTMLDivElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const multiline = ref(false)
const composing = ref(false)
let resizeObserver: ResizeObserver | null = null

const actionDisabled = computed(
  () =>
    props.disabled ||
    (!props.running &&
      (props.uploading > 0 ||
        (!props.modelValue.trim() && props.attachments.length === 0)))
)

const measure = () => {
  const element = editor.value
  if (!element) return
  const style = getComputedStyle(element)
  const lineHeight = Number.parseFloat(style.lineHeight) || 24
  const verticalPadding =
    Number.parseFloat(style.paddingTop) +
    Number.parseFloat(style.paddingBottom)
  multiline.value =
    element.scrollHeight - verticalPadding > lineHeight * 1.5
}

const syncEditor = () => {
  const element = editor.value
  if (!element || element.innerText === props.modelValue) return
  element.textContent = props.modelValue
  void nextTick(measure)
}

const updateValue = () => {
  const element = editor.value
  if (!element) return
  const value = element.textContent === "" ? "" : element.innerText
  emit("update:modelValue", value.replace(/\r\n/g, "\n"))
  measure()
}

const submit = () => {
  if (!actionDisabled.value && !props.running) emit("submit")
}

const runAction = () => {
  if (actionDisabled.value) return
  if (props.running) {
    emit("cancel")
    return
  }
  emit("submit")
}

const handleKeydown = (event: KeyboardEvent) => {
  if (
    event.key !== "Enter" ||
    event.shiftKey ||
    event.isComposing ||
    composing.value
  ) {
    return
  }
  event.preventDefault()
  submit()
}

const selectFiles = (files: FileList | File[]) => {
  const selected = Array.from(files)
  if (selected.length) emit("files-selected", selected)
}

const handleFileInput = (event: Event) => {
  const input = event.target as HTMLInputElement
  if (input.files) selectFiles(input.files)
  input.value = ""
}

const handleDrop = (event: DragEvent) => {
  if (props.disabled || !event.dataTransfer?.files.length) return
  selectFiles(event.dataTransfer.files)
}

const handlePaste = (event: ClipboardEvent) => {
  if (props.disabled || !event.clipboardData) return
  const files = Array.from(event.clipboardData.files)
  if (files.length === 0) {
    Array.from(event.clipboardData.items).forEach((item) => {
      const file = item.kind === "file" ? item.getAsFile() : null
      if (file) files.push(file)
    })
  }
  if (files.length === 0) return
  event.preventDefault()
  selectFiles(files)
}

watch(() => props.modelValue, syncEditor)

onMounted(() => {
  syncEditor()
  if (!editor.value) return
  resizeObserver = new ResizeObserver(measure)
  resizeObserver.observe(editor.value)
})

onBeforeUnmount(() => resizeObserver?.disconnect())
</script>

<template>
  <form
    class="flex w-full flex-col rounded-[1.7rem] border border-graphite/14 bg-paper p-2.5 shadow-[0_12px_36px_rgba(13,13,13,0.08)] transition-[border-color,box-shadow] duration-150 focus-within:border-graphite/24 focus-within:shadow-[0_14px_40px_rgba(13,13,13,0.11)] motion-reduce:transition-none"
    @submit.prevent="submit"
    @dragover.prevent
    @drop.prevent="handleDrop"
  >
    <ul
      v-if="attachments.length || uploading"
      class="m-0 flex w-full list-none flex-wrap gap-2 px-3 py-2.5"
    >
      <AttachmentComponent
        v-for="attachment in attachments"
        :key="attachment.file_id"
        :attachment="attachment"
        removable
        @remove="emit('remove-attachment', $event)"
      />

      <li
        v-if="uploading"
        class="flex h-11 items-center rounded-full bg-mist px-4 text-sm text-slate"
        role="status"
      >
        Uploading{{ uploading > 1 ? ` ${uploading} files` : '' }}…
      </li>
    </ul>

    <div
      class="grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-end gap-2"
    >
      <input
        ref="fileInput"
        class="hidden"
        type="file"
        multiple
        tabindex="-1"
        @change="handleFileInput"
      >

      <button
        class="grid size-10 shrink-0 place-items-center rounded-full bg-graphite/6 text-graphite transition-colors duration-150 hover:bg-graphite/10 disabled:cursor-not-allowed disabled:text-graphite/25 motion-reduce:transition-none"
        :class="{ 'col-start-1 row-start-2': multiline }"
        type="button"
        :disabled="disabled"
        aria-label="Add attachments"
        title="Add attachments"
        @click="fileInput?.click()"
      >
        <Paperclip
          :size="19"
          :stroke-width="1.9"
          aria-hidden="true"
        />
      </button>

      <div
        ref="editor"
        class="min-h-10 min-w-0 overflow-y-auto whitespace-pre-wrap break-words px-2 py-2 text-[0.95rem] leading-6 text-graphite outline-none empty:before:pointer-events-none empty:before:text-slate/70 empty:before:content-['Ask_anything']"
        :class="{
          'col-span-3 col-start-1 row-start-1 max-h-[180px]': multiline,
          'col-start-2 row-start-1 max-h-10': !multiline,
          'cursor-not-allowed opacity-60': disabled
        }"
        :contenteditable="disabled ? 'false' : 'plaintext-only'"
        role="textbox"
        aria-label="Message"
        aria-multiline="true"
        @compositionstart="composing = true"
        @compositionend="composing = false"
        @input="updateValue"
        @keydown="handleKeydown"
        @paste="handlePaste"
      />

      <button
        class="grid size-10 shrink-0 place-items-center rounded-full bg-graphite text-paper transition-colors duration-150 hover:bg-graphite/84 disabled:cursor-not-allowed disabled:bg-graphite/18 motion-reduce:transition-none"
        :class="{ 'col-start-3 row-start-2': multiline }"
        type="button"
        :disabled="actionDisabled"
        :aria-label="running ? 'Cancel response' : 'Send message'"
        :title="running ? 'Cancel' : 'Send'"
        @click="runAction"
      >
        <Square
          v-if="running"
          :size="14"
          :stroke-width="2"
          fill="currentColor"
          aria-hidden="true"
        />
        <ArrowUp
          v-else
          :size="19"
          :stroke-width="2.1"
          aria-hidden="true"
        />
      </button>
    </div>
  </form>
</template>
