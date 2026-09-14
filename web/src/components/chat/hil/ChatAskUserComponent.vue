<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { ChevronLeft, ChevronRight } from "@lucide/vue"

import type { InteractionRequired } from "@/types/chat"

const props = defineProps<{
  interaction: InteractionRequired
  disabled?: boolean
}>()

const emit = defineEmits<{
  submit: [answers: Record<string, string>]
}>()

const answers = ref<Record<string, string>>({})
const currentIndex = ref(0)
const direction = ref(1)
const question = computed(() => props.interaction.questions[currentIndex.value])
const questionHeading = ref<HTMLElement | null>(null)
const allAnswered = computed(() =>
  props.interaction.questions.length > 0 &&
  props.interaction.questions.every((question) =>
    question.options.some((option) => option.value === answers.value[question.question_id])
  )
)

watch(
  () => props.interaction.parent_run_id,
  () => {
    answers.value = {}
    currentIndex.value = 0
    direction.value = 1
  }
)

const goTo = (index: number) => {
  if (props.disabled || index < 0 || index >= props.interaction.questions.length) return
  direction.value = index > currentIndex.value ? 1 : -1
  currentIndex.value = index
}

const selectOption = (value: string) => {
  if (props.disabled || !question.value) return
  answers.value[question.value.question_id] = value
  goTo(currentIndex.value + 1)
}

const focusQuestion = () => questionHeading.value?.focus({ preventScroll: true })

const submit = () => {
  if (!allAnswered.value || props.disabled) return
  emit("submit", { ...answers.value })
}
</script>

<template>
  <article
    class="w-full max-w-[36rem] overflow-hidden rounded-[1.25rem] border border-graphite/10 bg-paper shadow-[0_18px_48px_rgba(13,13,13,0.08)]"
    aria-label="Agent questions"
  >
    <header class="flex items-center gap-3 border-b border-graphite/8 px-5 py-4">
      <span
        class="grid size-9 shrink-0 place-items-center rounded-full bg-graphite text-paper"
        aria-hidden="true"
      >
        <svg
          width="17"
          height="17"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.9"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M12 21a9 9 0 1 0-9-9" />
          <path d="M8.8 9a3.3 3.3 0 0 1 6.4 1.1c0 2.2-3.2 2.4-3.2 4.1" />
          <path d="M12 18h.01" />
        </svg>
      </span>
      <div>
        <p class="m-0 font-utility text-[0.66rem] font-bold tracking-[0.12em] text-slate uppercase">
          Input required
        </p>
        <p class="m-0 mt-0.5 text-sm font-semibold text-graphite">
          Agent needs your choice
        </p>
      </div>
    </header>

    <!-- ponytail: one local page, native radios and CSS transitions; no carousel state layer. -->
    <div class="relative h-[min(22rem,45dvh)] overflow-hidden">
      <Transition
        mode="out-in"
        enter-active-class="transition duration-150 ease-out motion-reduce:transition-none"
        leave-active-class="transition duration-100 ease-in motion-reduce:transition-none"
        :enter-from-class="direction > 0 ? 'translate-x-6 opacity-0 motion-reduce:translate-x-0' : '-translate-x-6 opacity-0 motion-reduce:translate-x-0'"
        :leave-to-class="direction > 0 ? '-translate-x-6 opacity-0 motion-reduce:translate-x-0' : 'translate-x-6 opacity-0 motion-reduce:translate-x-0'"
        @before-leave="(element) => element.setAttribute('inert', '')"
        @after-enter="focusQuestion"
      >
        <fieldset
          v-if="question"
          :key="`${interaction.parent_run_id}-${question.question_id}`"
          class="m-0 h-full min-w-0 overflow-y-auto overscroll-contain border-0 px-5 py-5"
          :disabled="disabled"
          :aria-labelledby="`ask-title-${interaction.parent_run_id}-${question.question_id}`"
        >
          <h3
            :id="`ask-title-${interaction.parent_run_id}-${question.question_id}`"
            ref="questionHeading"
            tabindex="-1"
            class="m-0 w-full break-words p-0 text-[0.95rem] font-medium leading-6 text-graphite focus-visible:outline-2 focus-visible:outline-offset-2"
          >
            {{ question.question }}
          </h3>

          <p class="mt-2 text-xs text-slate">选择后自动进入下一题，可用下方箭头返回修改。</p>

          <div class="mt-4 grid gap-2">
            <label
              v-for="option in question.options"
              :key="option.value"
              class="relative flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-50"
              :class="answers[question.question_id] === option.value
                ? 'border-graphite bg-graphite text-paper'
                : 'border-graphite/10 bg-mist/45 text-graphite hover:border-graphite/25'"
            >
              <input
                :checked="answers[question.question_id] === option.value"
                class="sr-only"
                type="radio"
                :name="`ask-user-${interaction.parent_run_id}-${question.question_id}`"
                :value="option.value"
                @click="answers[question.question_id] === option.value && selectOption(option.value)"
                @change="selectOption(option.value)"
              >
              <span
                class="grid size-4 shrink-0 place-items-center rounded-full border"
                :class="answers[question.question_id] === option.value
                  ? 'border-paper/70'
                  : 'border-graphite/25'"
                aria-hidden="true"
              >
                <span
                  v-if="answers[question.question_id] === option.value"
                  class="size-1.5 rounded-full bg-paper"
                />
              </span>
              <span class="min-w-0 break-words">{{ option.label }}</span>
            </label>
          </div>
        </fieldset>
      </Transition>
    </div>

    <footer class="flex items-center justify-between gap-3 border-t border-graphite/8 bg-mist/60 px-4 py-3">
      <nav class="flex items-center gap-2" aria-label="问题翻页">
        <button
          type="button"
          aria-label="上一题"
          class="grid size-11 place-items-center rounded-full border border-graphite/10 text-graphite hover:bg-paper focus-visible:outline-2 disabled:cursor-not-allowed disabled:opacity-35"
          :disabled="disabled || currentIndex === 0"
          @click="goTo(currentIndex - 1)"
        >
          <ChevronLeft :size="18" aria-hidden="true" />
        </button>
        <span class="min-w-10 text-center text-xs tabular-nums text-graphite" aria-live="polite" aria-atomic="true">
          {{ interaction.questions.length ? currentIndex + 1 : 0 }} / {{ interaction.questions.length }}
        </span>
        <button
          type="button"
          aria-label="下一题"
          class="grid size-11 place-items-center rounded-full border border-graphite/10 text-graphite hover:bg-paper focus-visible:outline-2 disabled:cursor-not-allowed disabled:opacity-35"
          :disabled="disabled || currentIndex >= interaction.questions.length - 1"
          @click="goTo(currentIndex + 1)"
        >
          <ChevronRight :size="18" aria-hidden="true" />
        </button>
      </nav>
      <button
        type="button"
        class="min-h-11 rounded-full bg-graphite px-4 py-2 text-sm font-semibold text-paper transition-opacity focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-35"
        :disabled="disabled || !allAnswered"
        @click="submit"
      >
        Continue
      </button>
    </footer>
  </article>
</template>
