<script setup lang="ts">
import { computed, h, type Component } from "vue"
import {
  Button as AButton,
  Drawer as ADrawer,
  message
} from "ant-design-vue"
import {
  Info,
  Map,
  PanelRightClose,
  PanelRightOpen,
  PanelsTopLeft,
  Presentation,
  X
} from "@lucide/vue"

import type { KnowledgePanelPresentation } from "@/types/knowledge"

import KnowledgeToolComponent from "./KnowledgeToolComponent.vue"

const props = defineProps<{
  collapsed: boolean
  presentation: KnowledgePanelPresentation
  open: boolean
}>()

const emit = defineEmits<{
  close: []
  "toggle-collapse": []
}>()

type KnowledgeToolTone = "road-map" | "ppt" | "slides"

const tools: Array<{
  id: KnowledgeToolTone
  label: string
  icon: Component
}> = [
  { id: "road-map", label: "Road Map", icon: Map },
  { id: "ppt", label: "PPT", icon: Presentation },
  { id: "slides", label: "Slides", icon: PanelsTopLeft }
]

const regionComponent = computed(() =>
  props.presentation === "drawer" ? ADrawer : "section"
)

const regionBindings = computed<Record<string, unknown>>(() => {
  if (props.presentation === "panel") return {}

  return {
    open: props.open,
    placement: "right",
    width: "min(23rem, calc(100vw - 1rem))",
    closable: false,
    keyboard: true,
    maskClosable: true,
    destroyOnClose: false,
    role: "dialog",
    "aria-modal": "true",
    "aria-labelledby": "knowledge-actions-title",
    rootClassName: "knowledge-actions-drawer",
    onClose: () => emit("close"),
    onAfterOpenChange: restoreTriggerFocus
  }
})

/** 抽屉关闭后将键盘焦点归还给工具入口。 */
function restoreTriggerFocus(open: boolean) {
  if (open || props.presentation !== "drawer") return

  document.querySelector<HTMLElement>("#knowledge-actions-trigger")?.focus()
}

/** 明确提示样例功能尚未连接生成服务。 */
function openTool(label: string) {
  void message.info({
    content: `${label} is not connected yet.`,
    icon: h(Info, {
      size: 16,
      strokeWidth: 1.8,
      "aria-hidden": "true"
    })
  })
}
</script>

<template>
  <component
    :is="regionComponent"
    v-bind="regionBindings"
    class="min-h-0 min-w-0"
  >
    <div
      id="knowledge-actions-region"
      class="knowledge-actions grid h-full min-h-0 min-w-0 overflow-hidden border border-graphite/10 bg-paper rounded-[16px] caret-transparent [grid-template-rows:48px_minmax(0,1fr)] focus-visible:outline-offset-[-3px]"
      :class="{
        'min-h-[calc(100dvh-1.3rem)]': props.presentation === 'drawer'
      }"
      tabindex="-1"
    >
      <header
        class="flex min-w-0 items-center justify-between h-12 min-h-12 max-h-12 border-b border-graphite/10 select-none caret-transparent transition-[padding-inline] duration-[240ms] ease-[cubic-bezier(0.65,0,0.35,1)] motion-reduce:transition-none"
        :class="{
          'px-4': !(props.presentation === 'panel' && props.collapsed),
          'px-[7px] max-[720px]:px-4':
            props.presentation === 'panel' && props.collapsed
        }"
      >
        <h2
          id="knowledge-actions-title"
          class="m-0 min-w-0 flex-1 overflow-hidden whitespace-nowrap font-semibold text-base tracking-[-0.025em] cursor-default select-none caret-transparent motion-reduce:transition-none"
          :class="{
            '[transition:opacity_140ms_ease_100ms,visibility_0s_linear]':
              !(props.presentation === 'panel' && props.collapsed),
            'opacity-0 invisible pointer-events-none [transition:opacity_80ms_ease,visibility_0s_linear_80ms] max-[720px]:opacity-100 max-[720px]:visible max-[720px]:pointer-events-auto max-[720px]:[transition:none]':
              props.presentation === 'panel' && props.collapsed
          }"
        >
          Tools
        </h2>
        <AButton
          v-if="props.presentation === 'panel'"
          class="knowledge-panel-collapse grid! shrink-0 place-items-center h-10! min-w-10! w-10! p-0! text-slate! hover:bg-graphite/8! hover:text-graphite! focus-visible:bg-graphite/8! focus-visible:text-graphite! max-[720px]:hidden"
          type="text"
          shape="circle"
          :aria-label="props.collapsed ? 'Expand tools' : 'Collapse tools'"
          :aria-expanded="!props.collapsed"
          aria-controls="knowledge-actions-body"
          :title="props.collapsed ? 'Expand tools' : 'Collapse tools'"
          @click="emit('toggle-collapse')"
        >
          <span
            class="grid place-items-center h-[18px] w-[18px] [&_svg]:block [&_svg]:h-[18px] [&_svg]:w-[18px]"
            aria-hidden="true"
          >
            <PanelRightOpen
              v-if="props.collapsed"
              :size="18"
              :stroke-width="1.8"
            />
            <PanelRightClose
              v-else
              :size="18"
              :stroke-width="1.8"
            />
          </span>
        </AButton>
        <AButton
          v-else
          class="knowledge-panel-close grid! shrink-0 place-items-center h-11! min-w-11! w-11! text-slate! hover:bg-graphite/8! hover:text-graphite! focus-visible:bg-graphite/8! focus-visible:text-graphite!"
          type="text"
          shape="circle"
          aria-label="Close tools"
          @click="emit('close')"
        >
          <X :size="18" :stroke-width="1.8" aria-hidden="true" />
        </AButton>
      </header>

      <div
        id="knowledge-actions-body"
        class="grid min-h-0 min-w-0 overflow-hidden [grid-template-rows:repeat(2,minmax(0,1fr))] motion-reduce:transition-none"
        :class="{
          '[transition:opacity_140ms_ease_100ms,visibility_0s_linear]':
            !(props.presentation === 'panel' && props.collapsed),
          'opacity-0 invisible pointer-events-none [transition:opacity_80ms_ease,visibility_0s_linear_80ms] max-[720px]:opacity-100 max-[720px]:visible max-[720px]:pointer-events-auto max-[720px]:[transition:none]':
            props.presentation === 'panel' && props.collapsed
        }"
      >
        <div
          class="grid content-start overflow-y-auto overscroll-contain min-w-0 min-h-0 p-4 [grid-template-columns:repeat(3,minmax(0,1fr))] [grid-auto-rows:74px] gap-2"
        >
          <KnowledgeToolComponent
            v-for="tool in tools"
            :key="tool.id"
            :icon="tool.icon"
            :label="tool.label"
            :tone="tool.id"
            @activate="openTool(tool.label)"
          />
        </div>

        <div
          class="min-w-0 min-h-0 p-4 overflow-hidden border-t border-graphite/10"
          aria-hidden="true"
        />
      </div>
    </div>
  </component>
</template>
