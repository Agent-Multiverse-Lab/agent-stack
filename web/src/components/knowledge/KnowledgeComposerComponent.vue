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
  <form class="knowledge-composer" @submit.prevent="submitQuestion">
    <div class="knowledge-composer-controls">
      <ATextarea
        v-model:value="draft"
        class="knowledge-composer-input"
        :disabled="!props.enabled"
        :auto-size="{ minRows: 1, maxRows: 5 }"
        placeholder="Ask a question"
        aria-label="Ask this knowledge base"
        @keydown="handleKeydown"
      />

      <ATooltip
        :title="props.enabled ? 'Send' : 'Unavailable'"
      >
        <span class="knowledge-composer-submit-wrap">
          <AButton
            class="knowledge-composer-submit"
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

<style scoped>
@reference "../../styles/index.css";

.knowledge-composer {
  padding: 0.8rem;
  border-top: 1px solid var(--color-border-subtle);
  background: var(--color-surface);
}

.knowledge-composer-controls {
  @apply grid items-end border;

  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.5rem;
  padding: 0.45rem 0.5rem 0.45rem 0.8rem;
  border-color: var(--color-border-control);
  border-radius: var(--radius-knowledge-container);
  background: var(--color-surface-muted);
}

.knowledge-composer-controls:focus-within {
  border-color: var(--color-border-focus);
}

.knowledge-composer-input {
  @apply p-0;
}

.knowledge-composer-input :deep(textarea),
.knowledge-composer-input.ant-input {
  min-height: 2.1rem !important;
  padding: 0.38rem 0 !important;
  border: 0 !important;
  color: var(--color-text);
  background: transparent !important;
  box-shadow: none !important;
  line-height: 1.5;
  resize: none;
  user-select: text;
  caret-color: auto;
}

.knowledge-composer-input.ant-input-disabled {
  color: var(--color-text-subtle);
}

.knowledge-composer-input::placeholder,
.knowledge-composer-input :deep(textarea::placeholder) {
  color: var(--color-text-subtle);
}

.knowledge-composer-submit-wrap {
  @apply inline-grid;
}

.knowledge-composer-submit {
  @apply grid place-items-center;

  width: 2.75rem;
  min-width: 2.75rem;
  height: 2.75rem;
  border-color: var(--color-action-primary);
  color: var(--color-on-action);
  background: var(--color-action-primary);
  box-shadow: none;
}

.knowledge-composer-submit:not(:disabled):hover {
  border-color: var(--color-action-primary-hover);
  background: var(--color-action-primary-hover);
}

.knowledge-composer-submit:disabled {
  border-color: var(--color-border);
  color: var(--color-text-subtle);
  background: var(--color-surface-emphasis);
}

@media (max-width: 720px) {
  .knowledge-composer-input :deep(textarea),
  .knowledge-composer-input.ant-input {
    font-size: 1rem;
  }
}
</style>
