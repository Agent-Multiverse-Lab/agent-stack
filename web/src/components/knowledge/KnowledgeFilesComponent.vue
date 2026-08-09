<script setup lang="ts">
import { computed, h, ref, watch } from "vue"
import {
  Button as AButton,
  Drawer as ADrawer,
  Input as AInput,
  message,
  Upload,
  UploadDragger,
  type UploadProps
} from "ant-design-vue"
import {
  Globe,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  TriangleAlert,
  X
} from "@lucide/vue"

import type {
  KnowledgeFileItem,
  KnowledgePanelPresentation
} from "@/types/knowledge"

import KnowledgeFileListComponent from "./KnowledgeFileListComponent.vue"

const props = defineProps<{
  files: KnowledgeFileItem[]
  selectedFileId: string | null
  collapsed: boolean
  presentation: KnowledgePanelPresentation
  open: boolean
}>()

const emit = defineEmits<{
  "files-selected": [files: File[]]
  select: [fileId: string]
  remove: [fileId: string]
  close: []
  "toggle-collapse": []
}>()

const acceptedExtensions = new Set([
  "pdf",
  "doc",
  "docx",
  "txt",
  "md",
  "markdown",
  "csv",
  "xls",
  "xlsx",
  "ppt",
  "pptx",
  "png",
  "jpg",
  "jpeg",
  "webp"
])

const searchQuery = ref("")
const appliedSearchQuery = ref("")

const visibleFiles = computed(() => {
  const query = appliedSearchQuery.value.toLowerCase()
  if (!query) return props.files

  return props.files.filter((file) =>
    file.name.toLowerCase().includes(query)
  )
})

watch(searchQuery, (query) => {
  if (!query.trim()) appliedSearchQuery.value = ""
})

const regionComponent = computed(() =>
  props.presentation === "drawer" ? ADrawer : "section"
)

const regionBindings = computed<Record<string, unknown>>(() => {
  if (props.presentation === "panel") return {}

  return {
    open: props.open,
    placement: "left",
    width: "min(23rem, calc(100vw - 1rem))",
    closable: false,
    keyboard: true,
    maskClosable: true,
    destroyOnClose: false,
    role: "dialog",
    "aria-modal": "true",
    "aria-labelledby": "knowledge-files-title",
    rootClassName: "knowledge-files-drawer",
    onClose: () => emit("close"),
    onAfterOpenChange: restoreTriggerFocus
  }
})

/** 抽屉关闭后将键盘焦点归还给文件入口。 */
function restoreTriggerFocus(open: boolean) {
  if (open || props.presentation !== "drawer") return

  document.querySelector<HTMLElement>("#knowledge-files-trigger")?.focus()
}

/** 接收浏览器选择的文件，但阻止组件发起尚未接通的上传请求。 */
const selectFile: UploadProps["beforeUpload"] = (file) => {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? ""
  if (!acceptedExtensions.has(extension)) {
    void message.warning({
      content: `${file.name} is not a supported source type.`,
      icon: h(TriangleAlert, {
        size: 16,
        strokeWidth: 1.8,
        "aria-hidden": "true"
      })
    })
    return Upload.LIST_IGNORE
  }

  emit("files-selected", [file as File])
  return Upload.LIST_IGNORE
}

/** 提交当前输入，并按文件名更新列表过滤条件。 */
function submitSearch() {
  const query = searchQuery.value.trim()
  if (!query) return

  appliedSearchQuery.value = query
}
</script>

<template>
  <component
    :is="regionComponent"
    v-bind="regionBindings"
    class="min-h-0 min-w-0"
  >
    <div
      id="knowledge-files-region"
      class="knowledge-files grid h-full min-h-0 min-w-0 overflow-hidden border border-graphite/10 rounded-[16px] bg-paper caret-transparent [grid-template-rows:48px_minmax(0,1fr)] focus-visible:outline-offset-[-3px]"
      :class="{
        'min-h-[calc(100dvh-1.3rem)]': props.presentation === 'drawer'
      }"
      tabindex="-1"
    >
      <header
        class="flex h-12 min-h-12 max-h-12 min-w-0 items-center justify-between border-b border-graphite/6 select-none caret-transparent transition-[padding-inline] duration-[240ms] ease-[cubic-bezier(0.65,0,0.35,1)] motion-reduce:transition-none"
        :class="{
          'px-4': !(props.presentation === 'panel' && props.collapsed),
          'px-[7px] max-[720px]:px-4':
            props.presentation === 'panel' && props.collapsed
        }"
      >
        <h2
          id="knowledge-files-title"
          class="m-0 min-w-0 flex-1 cursor-default overflow-hidden whitespace-nowrap font-semibold text-base tracking-[-0.025em] select-none caret-transparent motion-reduce:transition-none"
          :class="{
            'opacity-100 visible transition-opacity duration-140 delay-100':
              !(props.presentation === 'panel' && props.collapsed),
            'opacity-0 invisible pointer-events-none transition-[opacity,visibility] duration-[80ms,0s] delay-[0ms,80ms] max-[720px]:opacity-100 max-[720px]:visible max-[720px]:pointer-events-auto max-[720px]:transition-none':
              props.presentation === 'panel' && props.collapsed
          }"
        >
          Files
        </h2>
        <AButton
          v-if="props.presentation === 'panel'"
          class="knowledge-panel-collapse grid! h-10! w-10! min-w-10! shrink-0 place-items-center p-0! text-slate! hover:bg-graphite/8! hover:text-graphite! focus-visible:bg-graphite/8! focus-visible:text-graphite! max-[720px]:hidden"
          type="text"
          shape="circle"
          :aria-label="props.collapsed ? 'Expand files' : 'Collapse files'"
          :aria-expanded="!props.collapsed"
          aria-controls="knowledge-files-body"
          :title="props.collapsed ? 'Expand files' : 'Collapse files'"
          @click="emit('toggle-collapse')"
        >
          <span class="grid h-[18px] w-[18px] place-items-center" aria-hidden="true">
            <PanelLeftOpen
              v-if="props.collapsed"
              :size="18"
              :stroke-width="1.8"
            />
            <PanelLeftClose
              v-else
              :size="18"
              :stroke-width="1.8"
            />
          </span>
        </AButton>
        <AButton
          v-else
          class="knowledge-panel-close grid! h-11! w-11! min-w-11! shrink-0 place-items-center text-slate! hover:bg-graphite/8! hover:text-graphite! focus-visible:bg-graphite/8! focus-visible:text-graphite!"
          type="text"
          shape="circle"
          aria-label="Close files"
          @click="emit('close')"
        >
          <X :size="18" :stroke-width="1.8" aria-hidden="true" />
        </AButton>
      </header>

      <div
        id="knowledge-files-body"
        class="grid min-h-0 min-w-0 gap-[0.8rem] p-[0.9rem] [grid-template-rows:auto_auto_minmax(0,1fr)] motion-reduce:transition-none"
        :class="{
          'opacity-100 visible transition-opacity duration-140 delay-100':
            !(props.presentation === 'panel' && props.collapsed),
          'opacity-0 invisible pointer-events-none transition-[opacity,visibility] duration-[80ms,0s] delay-[0ms,80ms] max-[720px]:opacity-100 max-[720px]:visible max-[720px]:pointer-events-auto max-[720px]:transition-none':
            props.presentation === 'panel' && props.collapsed
        }"
      >
        <UploadDragger
          class="knowledge-file-add block"
          name="knowledge-file"
          accept=".pdf,.doc,.docx,.txt,.md,.markdown,.csv,.xls,.xlsx,.ppt,.pptx,.png,.jpg,.jpeg,.webp"
          multiple
          :before-upload="selectFile"
          :show-upload-list="false"
        >
          <div class="flex items-center gap-[0.65rem] text-left">
            <span class="grid h-[2.15rem] w-[2.15rem] shrink-0 place-items-center rounded-[16px] border border-graphite/10 bg-paper text-graphite" aria-hidden="true">
              <Plus :size="18" :stroke-width="1.8" />
            </span>
            <strong class="flex min-w-0 items-center self-stretch font-semibold leading-none tracking-[-0.01em] text-graphite">Add Sources</strong>
          </div>
        </UploadDragger>

        <form
          class="grid min-w-0 gap-1 rounded-[16px] border border-graphite/16 bg-paper p-[0.45rem] [grid-template-rows:minmax(2.4rem,auto)_2rem] transition-colors duration-140 focus-within:border-graphite/22"
          role="search"
          @submit.prevent="submitSearch"
        >
          <AInput
            v-model:value="searchQuery"
            class="knowledge-file-search-input max-[720px]:text-base"
            type="text"
            inputmode="text"
            :bordered="false"
            aria-label="Search files"
            placeholder="Search files"
          />

          <div class="flex min-w-0 items-center justify-between">
            <span class="grid h-8 w-8 shrink-0 place-items-center text-slate" aria-hidden="true">
              <Globe :size="18" :stroke-width="1.8" />
            </span>

            <AButton
              class="grid! h-8! w-8! min-w-8! shrink-0 place-items-center border-graphite! bg-graphite! p-0! text-paper! shadow-none! hover:border-graphite/86! hover:bg-graphite/86! hover:text-paper! focus-visible:border-graphite/86! focus-visible:bg-graphite/86! focus-visible:text-paper!"
              type="primary"
              shape="circle"
              html-type="submit"
              aria-label="Search"
            >
              <Search :size="18" :stroke-width="2" aria-hidden="true" />
            </AButton>
          </div>
        </form>

        <div class="min-h-0 overflow-y-auto overscroll-contain">
          <KnowledgeFileListComponent
            :files="visibleFiles"
            :selected-file-id="props.selectedFileId"
            @select="emit('select', $event)"
            @remove="emit('remove', $event)"
          />
        </div>
      </div>
    </div>
  </component>
</template>
