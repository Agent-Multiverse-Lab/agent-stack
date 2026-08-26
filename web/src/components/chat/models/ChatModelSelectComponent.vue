<script setup lang="ts">
import {
  computed,
  onBeforeUnmount,
  onMounted,
  ref,
  type Component
} from "vue"
import {
  Atom,
  Bot,
  Check,
  ChevronDown,
  Gem,
  Search,
  Sparkles
} from "@lucide/vue"

import type { ChatModelOption } from "@/types/model"

const props = withDefaults(defineProps<{
  modelValue: string
  models: ChatModelOption[]
  loading?: boolean
  disabled?: boolean
  placement?: "top" | "bottom"
}>(), {
  loading: false,
  disabled: false,
  placement: "top"
})

const emit = defineEmits<{
  "update:modelValue": [modelId: string]
}>()

const iconComponents: Record<string, Component> = {
  qwen: Sparkles,
  deepseek: Search,
  openai: Atom,
  gemini: Gem
}

const container = ref<HTMLDivElement | null>(null)
const open = ref(false)

const selectedModel = computed(() =>
  props.models.find((model) => model.id === props.modelValue) ?? null
)

const controlDisabled = computed(
  () => props.disabled || props.loading || props.models.length === 0
)

const modelIcon = (icon: string) => iconComponents[icon] ?? Bot

const toggle = () => {
  if (!controlDisabled.value) open.value = !open.value
}

const selectModel = (model: ChatModelOption) => {
  if (!model.is_available) return
  emit("update:modelValue", model.id)
  open.value = false
}

const handleClickOutside = (event: MouseEvent) => {
  if (open.value && !container.value?.contains(event.target as Node)) {
    open.value = false
  }
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === "Escape") open.value = false
}

onMounted(() => {
  window.addEventListener("click", handleClickOutside)
  window.addEventListener("keydown", handleKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener("click", handleClickOutside)
  window.removeEventListener("keydown", handleKeydown)
})
</script>

<template>
  <div
    ref="container"
    class="relative min-w-0"
  >
    <button
      type="button"
      class="flex h-10 max-w-[13rem] min-w-0 items-center gap-2 rounded-full border border-graphite/8 bg-graphite/[0.035] pr-2.5 pl-1.5 text-left transition-colors duration-150 hover:border-graphite/14 hover:bg-graphite/[0.065] disabled:cursor-not-allowed disabled:opacity-45 motion-reduce:transition-none"
      :disabled="controlDisabled"
      :aria-expanded="open"
      aria-haspopup="listbox"
      aria-label="Select model"
      @click.stop="toggle"
    >
      <span
        class="grid size-7 shrink-0 place-items-center rounded-full border border-graphite/8 bg-paper text-graphite"
        aria-hidden="true"
      >
        <component
          :is="selectedModel ? modelIcon(selectedModel.icon) : Bot"
          :size="14"
          :stroke-width="1.9"
        />
      </span>

      <span class="flex min-w-0 items-baseline gap-1.5">
        <strong class="shrink-0 text-xs font-semibold text-graphite">
          {{ loading ? "Models" : selectedModel?.display_name ?? "Default" }}
        </strong>
        <span class="min-w-0 truncate font-utility text-[10.5px] text-slate">
          {{ loading ? "Loading" : selectedModel?.version ?? "Auto" }}
        </span>
      </span>

      <ChevronDown
        class="ml-auto shrink-0 text-slate transition-transform duration-150 motion-reduce:transition-none"
        :class="{ 'rotate-180': open }"
        :size="13"
        :stroke-width="2"
        aria-hidden="true"
      />
    </button>

    <Transition
      enter-active-class="transition duration-150 ease-out motion-reduce:transition-none"
      enter-from-class="translate-y-1 scale-[0.98] opacity-0 motion-reduce:translate-y-0 motion-reduce:scale-100"
      leave-active-class="transition duration-100 ease-in motion-reduce:transition-none"
      leave-to-class="translate-y-1 scale-[0.98] opacity-0 motion-reduce:translate-y-0 motion-reduce:scale-100"
    >
      <div
        v-if="open"
        class="absolute left-0 z-60 w-[min(21rem,calc(100vw-2rem))] overflow-hidden rounded-[16px] border border-graphite/12 bg-paper/96 p-1.5 shadow-[0_18px_44px_rgba(13,13,13,0.14)] backdrop-blur-md"
        :class="placement === 'top' ? 'bottom-full mb-2' : 'top-full mt-2'"
        role="listbox"
        aria-label="Available models"
      >
        <button
          v-for="model in models"
          :key="model.id"
          type="button"
          class="flex w-full items-center gap-3 rounded-[11px] px-2.5 py-2 text-left transition-colors duration-100 hover:bg-mist disabled:cursor-not-allowed disabled:opacity-40 motion-reduce:transition-none"
          :class="{ 'bg-graphite/[0.045]': model.id === modelValue }"
          :disabled="!model.is_available"
          role="option"
          :aria-selected="model.id === modelValue"
          @click="selectModel(model)"
        >
          <span
            class="grid size-8 shrink-0 place-items-center rounded-[10px] border border-graphite/8 bg-paper text-graphite shadow-[0_2px_8px_rgba(13,13,13,0.05)]"
            aria-hidden="true"
          >
            <component
              :is="modelIcon(model.icon)"
              :size="15"
              :stroke-width="1.8"
            />
          </span>

          <span class="min-w-0 flex-1">
            <span class="flex min-w-0 items-baseline gap-2">
              <strong class="shrink-0 text-[12.5px] font-semibold text-graphite">
                {{ model.display_name }}
              </strong>
              <span class="min-w-0 truncate font-utility text-[11px] text-slate">
                {{ model.version }}
              </span>
            </span>
            <span class="mt-0.5 block truncate text-[10.5px] text-slate/75">
              {{ model.provider }}{{ model.is_available ? "" : " · Unavailable" }}
            </span>
          </span>

          <Check
            v-if="model.id === modelValue"
            class="shrink-0 text-graphite"
            :size="15"
            :stroke-width="2.2"
            aria-hidden="true"
          />
        </button>
      </div>
    </Transition>
  </div>
</template>
