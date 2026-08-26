<script setup lang="ts">
import { computed } from "vue"
import {
  ChevronDown,
  Circle,
  CircleCheck,
  LoaderCircle
} from "@lucide/vue"

type TodoStatus = "pending" | "in_progress" | "completed"

type AgentTodo = Record<string, unknown> & {
  content: string
  status: TodoStatus
}

const props = defineProps<{
  event: unknown
}>()

const statusLabels: Record<TodoStatus, string> = {
  pending: "Pending",
  in_progress: "In progress",
  completed: "Completed"
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null

const isTodoStatus = (value: unknown): value is TodoStatus =>
  value === "pending" || value === "in_progress" || value === "completed"

const isAgentTodo = (value: unknown): value is AgentTodo =>
  isRecord(value) &&
  typeof value.content === "string" &&
  value.content.trim().length > 0 &&
  isTodoStatus(value.status)

const todos = computed<AgentTodo[]>(() => {
  if (!isRecord(props.event) || !isRecord(props.event.agent_state)) return []

  const agentTodos = props.event.agent_state.agent_todo
  return Array.isArray(agentTodos) ? agentTodos.filter(isAgentTodo) : []
})

const completedCount = computed(
  () => todos.value.filter((todo) => todo.status === "completed").length
)

const summary = computed(() => {
  const count = todos.value.length
  if (count === 0) return "Agent tasks"
  return `${count} ${count === 1 ? "task" : "tasks"} · ${completedCount.value} completed`
})

const formattedTodo = (todo: AgentTodo) => JSON.stringify(todo, null, 2)
</script>

<template>
  <details
    class="agent-tool-group w-full max-w-2xl text-sm"
    open
  >
    <summary
      class="agent-tool-group__summary -ml-1.5 flex w-fit cursor-pointer list-none items-center gap-1.5 rounded-md px-1.5 py-1 text-[12.5px] text-slate transition-colors duration-100 hover:bg-mist hover:text-graphite focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-graphite/35 [&::-webkit-details-marker]:hidden"
    >
      <ChevronDown
        class="agent-tool-group__chevron shrink-0"
        :size="13"
        :stroke-width="2.2"
        aria-hidden="true"
      />
      <span class="tabular-nums">{{ summary }}</span>
    </summary>

    <div
      v-if="todos.length"
      class="mt-1.5 flex flex-col gap-1"
      aria-live="polite"
    >
      <details
        v-for="(todo, index) in todos"
        :key="`${todo.status}-${todo.content}-${index}`"
        class="agent-tool-row"
      >
        <summary
          class="agent-tool-row__summary flex h-7 min-w-0 cursor-pointer list-none items-center gap-2 rounded-md px-1 text-left transition-colors duration-100 hover:bg-mist focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-graphite/35 [&::-webkit-details-marker]:hidden"
        >
          <span
            class="agent-tool-row__icon relative flex size-4 shrink-0 items-center justify-center"
            :class="{
              'text-graphite/45': todo.status === 'pending',
              'text-graphite': todo.status === 'in_progress',
              'text-slate': todo.status === 'completed'
            }"
            aria-hidden="true"
          >
            <Circle
              v-if="todo.status === 'pending'"
              class="agent-tool-row__status-icon"
              :size="13"
              :stroke-width="1.9"
            />
            <LoaderCircle
              v-else-if="todo.status === 'in_progress'"
              class="agent-tool-row__status-icon motion-safe:animate-spin"
              :size="13"
              :stroke-width="2"
            />
            <CircleCheck
              v-else
              class="agent-tool-row__status-icon"
              :size="13"
              :stroke-width="1.9"
            />
            <ChevronDown
              class="agent-tool-row__chevron absolute"
              :size="12"
              :stroke-width="2.2"
            />
          </span>

          <span class="shrink-0 text-[12.5px] font-medium text-graphite">
            {{ statusLabels[todo.status] }}
          </span>
          <span
            class="inline-flex h-5.5 min-w-0 flex-1 items-center truncate rounded-md bg-mist px-1.5 text-[11.5px] text-slate shadow-[inset_0_0_0_1px_rgb(13_13_13/0.05)]"
          >
            {{ todo.content }}
          </span>
        </summary>

        <div class="mt-0.5 mb-1 ml-2 border-l border-graphite/10 py-1 pl-3.5">
          <pre class="m-0 overflow-x-auto font-mono text-[11.5px] leading-5 text-slate">{{ formattedTodo(todo) }}</pre>
        </div>
      </details>
    </div>

    <p
      v-else
      class="mt-1.5 mb-0 px-1 text-xs text-slate"
    >
      No task state reported.
    </p>
  </details>
</template>

<style scoped>
.agent-tool-group__chevron,
.agent-tool-row__chevron,
.agent-tool-row__status-icon {
  transition:
    opacity 150ms ease,
    transform 150ms ease;
}

.agent-tool-group__chevron,
.agent-tool-row__chevron {
  transform: rotate(-90deg);
}

.agent-tool-group[open]
  > .agent-tool-group__summary
  .agent-tool-group__chevron,
.agent-tool-row[open]
  > .agent-tool-row__summary
  .agent-tool-row__chevron {
  transform: rotate(0deg);
}

.agent-tool-row__chevron {
  opacity: 0;
}

.agent-tool-row__summary:hover .agent-tool-row__status-icon,
.agent-tool-row[open]
  > .agent-tool-row__summary
  .agent-tool-row__status-icon {
  opacity: 0;
}

.agent-tool-row__summary:hover .agent-tool-row__chevron,
.agent-tool-row[open]
  > .agent-tool-row__summary
  .agent-tool-row__chevron {
  opacity: 1;
}

@media (prefers-reduced-motion: reduce) {
  .agent-tool-group__chevron,
  .agent-tool-row__chevron,
  .agent-tool-row__status-icon {
    transition: none;
  }
}
</style>
