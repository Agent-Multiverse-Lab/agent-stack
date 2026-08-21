<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch
} from "vue"
import { ArrowUp, Square } from "@lucide/vue"
import { Tooltip as ATooltip } from "ant-design-vue"

import AttachmentComponent from "@/components/AttachmentComponent.vue"
import ChatActionMenuComponent from "@/components/chat/ChatActionMenuComponent.vue"
import type { UploadedAttachmentResponse } from "@/types/attachment"

const props = defineProps<{
  modelValue: string
  attachments: UploadedAttachmentResponse[]
  uploading: number
  running: boolean
  disabled: boolean
  actionMenuPlacement: "top" | "bottom"
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
    class="relative flex w-full flex-col rounded-[1.7rem] border border-graphite/14 bg-paper p-2 shadow-[0_10px_28px_rgba(13,13,13,0.07)] transition-[border-color,box-shadow] duration-150 focus-within:border-graphite/24 focus-within:shadow-[0_12px_32px_rgba(13,13,13,0.1)] motion-reduce:transition-none"
    @submit.prevent="submit" @dragover.prevent @drop.prevent="handleDrop">
    <TransitionGroup v-if="attachments.length || uploading" tag="ul"
      class="m-0 flex w-full list-none flex-wrap gap-2 px-3 py-2.5"
      enter-active-class="transition-[opacity,transform] duration-150 ease-out motion-reduce:transition-none"
      enter-from-class="translate-y-1 scale-[0.97] opacity-0 motion-reduce:translate-y-0 motion-reduce:scale-100"
      leave-active-class="transition-[opacity,transform] duration-150 ease-in motion-reduce:transition-none"
      leave-to-class="-translate-y-1 scale-[0.97] opacity-0 motion-reduce:translate-y-0 motion-reduce:scale-100"
      move-class="transition-transform duration-150 ease-out motion-reduce:transition-none">
      <AttachmentComponent v-for="attachment in attachments" :key="attachment.file_id" :attachment="attachment"
        removable @remove="emit('remove-attachment', $event)" />

      <li v-if="uploading" key="uploading" class="flex h-11 items-center rounded-full bg-mist px-4 text-sm text-slate"
        role="status">
        Uploading{{ uploading > 1 ? ` ${uploading} files` : '' }}…
      </li>
    </TransitionGroup>

    <div class="grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-end gap-2">
      <input ref="fileInput" class="hidden" type="file" multiple tabindex="-1" @change="handleFileInput">

      <ChatActionMenuComponent :class="{ 'col-start-1 row-start-2': multiline }" :disabled="disabled"
        :placement="actionMenuPlacement" @select-attachment="fileInput?.click()" />

      <div ref="editor"
        class="min-h-10 min-w-0 overflow-y-auto whitespace-pre-wrap break-words px-2 py-2 text-[0.95rem] leading-6 text-graphite outline-none empty:before:pointer-events-none empty:before:text-slate/70 empty:before:content-['Ask_anything']"
        :class="{
          'col-span-3 col-start-1 row-start-1 max-h-[180px]': multiline,
          'col-start-2 row-start-1 max-h-10': !multiline,
          'cursor-not-allowed opacity-60': disabled
        }" :contenteditable="disabled ? 'false' : 'plaintext-only'" role="textbox" aria-label="Message"
        aria-multiline="true" @compositionstart="composing = true" @compositionend="composing = false"
        @input="updateValue" @keydown="handleKeydown" @paste="handlePaste" />

      <ATooltip placement="top" :title="running ? 'Cancel' : 'Send'">
        <button
          class="grid size-10 shrink-0 place-items-center rounded-full bg-graphite text-paper transition-colors duration-150 hover:bg-graphite/84 disabled:cursor-not-allowed disabled:bg-graphite/18 motion-reduce:transition-none"
          :class="{ 'col-start-3 row-start-2': multiline }" type="button" :disabled="actionDisabled"
          :aria-label="running ? 'Cancel response' : 'Send message'" @click="runAction">
          <Transition mode="out-in"
            enter-active-class="transition-[opacity,transform] [transition-duration:120ms] ease-out motion-reduce:transition-none"
            enter-from-class="scale-75 opacity-0 motion-reduce:scale-100"
            leave-active-class="transition-[opacity,transform] [transition-duration:120ms] ease-in motion-reduce:transition-none"
            leave-to-class="scale-75 opacity-0 motion-reduce:scale-100">
            <Square v-if="running" key="cancel" :size="14" :stroke-width="2" fill="currentColor" aria-hidden="true" />
            <ArrowUp v-else key="send" :size="19" :stroke-width="2.1" aria-hidden="true" />
          </Transition>
        </button>
      </ATooltip>
    </div>
  </form>
</template>
