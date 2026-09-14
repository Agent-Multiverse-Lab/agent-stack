<script setup lang="ts">
import { computed, ref, watch } from "vue"

import type { InteractionRequired } from "@/types/chat"

const props = defineProps<{
  interaction: InteractionRequired
  disabled?: boolean
}>()

const emit = defineEmits<{
  submit: [answers: Record<string, string>]
}>()

const answers = ref<Record<string, string>>({})
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
  }
)

const submit = () => {
  if (!allAnswered.value || props.disabled) return
  emit("submit", { ...answers.value })
}
</script>

<template>
  <!-- FIXEME: 问题和选项完全来自真实 interrupt payload。 -->
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

    <fieldset
      v-for="question in interaction.questions"
      :key="question.question_id"
      class="m-0 min-w-0 border-0 px-5 py-5"
      :disabled="disabled"
    >
      <legend
        class="w-full break-words p-0 text-[0.95rem] font-medium leading-6 text-graphite"
      >
        {{ question.question }}
      </legend>

      <div class="mt-4 grid gap-2">
        <label
          v-for="option in question.options"
          :key="option.value"
          class="flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm transition-colors"
          :class="answers[question.question_id] === option.value
            ? 'border-graphite bg-graphite text-paper'
            : 'border-graphite/10 bg-mist/45 text-graphite hover:border-graphite/25'"
        >
          <input
            v-model="answers[question.question_id]"
            class="sr-only"
            type="radio"
            :name="`ask-user-${interaction.parent_run_id}-${question.question_id}`"
            :value="option.value"
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

    <footer class="flex justify-end border-t border-graphite/8 bg-mist/60 px-4 py-3">
      <button
        type="button"
        class="rounded-full bg-graphite px-4 py-2 text-sm font-semibold text-paper transition-opacity disabled:cursor-not-allowed disabled:opacity-35"
        :disabled="disabled || !allAnswered"
        @click="submit"
      >
        Continue
      </button>
    </footer>
  </article>
</template>
