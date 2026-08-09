<script setup lang="ts">
import { computed, ref } from "vue"
import {
  Button as AButton,
  Textarea as ATextarea,
  Tooltip as ATooltip
} from "ant-design-vue"
import { ArrowUp, LockKeyhole } from "@lucide/vue"

const props = defineProps<{
  enabled: boolean
}>()

const emit = defineEmits<{
  submit: [question: string]
}>()

const draft = ref("")

const canSubmit = computed(
  () => props.enabled && draft.value.trim().length > 0
)

/** 提交已经具备索引上下文的知识库问题。 */
const submitQuestion = () => {
  if (!canSubmit.value) return

  emit("submit", draft.value.trim())
  draft.value = ""
}

/** 使用 Enter 提交，Shift+Enter 保留换行。 */
const handleKeydown = (event: KeyboardEvent) => {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return

  event.preventDefault()
  submitQuestion()
}
</script>

<template>
  <form
    class="border-t border-graphite/6 bg-paper p-[0.8rem]"
    @submit.prevent="submitQuestion"
  >
    <div
      class="grid items-end gap-2 rounded-[16px] border border-graphite/16 bg-mist py-[0.45rem] pr-2 pl-[0.8rem] [grid-template-columns:minmax(0,1fr)_auto] focus-within:border-graphite/22"
    >
      <ATextarea
        v-model:value="draft"
        class="knowledge-composer-input max-[720px]:text-base"
        :disabled="!props.enabled"
        :auto-size="{ minRows: 1, maxRows: 5 }"
        placeholder="Ask a question"
        aria-label="Ask this knowledge base"
        @keydown="handleKeydown"
      />

      <ATooltip
        :title="props.enabled ? 'Send' : 'Unavailable'"
      >
        <span class="inline-grid">
          <AButton
            class="knowledge-composer-submit grid! h-11! w-11! min-w-11! place-items-center border-graphite! bg-graphite! text-paper! shadow-none! enabled:hover:border-graphite/86! enabled:hover:bg-graphite/86! disabled:border-graphite/10! disabled:bg-graphite/6! disabled:text-graphite/58!"
            type="primary"
            shape="circle"
            html-type="submit"
            :disabled="!canSubmit"
            aria-label="Send question"
          >
            <ArrowUp
              v-if="props.enabled"
              :size="17"
              :stroke-width="2"
              aria-hidden="true"
            />
            <LockKeyhole
              v-else
              :size="15"
              :stroke-width="1.9"
              aria-hidden="true"
            />
          </AButton>
        </span>
      </ATooltip>
    </div>
  </form>
</template>
