import { useState } from "react"
import { Check, ChevronsUpDown, ListTodo, LoaderCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useTranslation } from "@/i18n"
import type { AgentTodoItem } from "@/pages/chat/types"

interface AgentTasksSectionProps {
  todos: AgentTodoItem[]
}

export function AgentTasksSection({ todos }: AgentTasksSectionProps) {
  const { t } = useTranslation()
  const [manualOpen, setManualOpen] = useState<Record<string, boolean>>({})

  if (!todos.length) return null

  const completedCount = todos.filter((item) => item.status === "completed").length
  const allCompleted = completedCount === todos.length

  return (
    <div
      data-task-group-status={allCompleted ? "completed" : "running"}
      className="flex w-full min-w-0 flex-col gap-1 self-start"
    >
      <div className="flex h-7 items-center justify-between p-0 text-xs text-muted-foreground/60">
        <span className="flex items-center gap-1.5 text-[13px] font-medium text-muted-foreground/90">
          <ListTodo className="size-3.5 text-muted-foreground/60" />
          {t(todos.length === 1 ? "{{tasks}} task" : "{{tasks}} tasks", {
            tasks: todos.length,
          })}
        </span>
        <span className="tabular-nums text-[12px] text-muted-foreground/60">
          {t("{{completed}} completed", {
            completed: completedCount,
          })}
        </span>
      </div>

      <div className="flex flex-col gap-0.5">
        {todos.map((todo, i) => {
          const rowKey = `${todo.content}-${i}`
          const open = manualOpen[rowKey] ?? false
          const statusLabel =
            todo.status === "in_progress"
              ? t("In progress")
              : todo.status === "completed"
                ? t("Completed")
                : t("Pending")

          return (
            <div key={rowKey} className="w-full self-stretch">
              <Button
                type="button"
                variant="ghost"
                aria-expanded={open}
                onClick={() =>
                  setManualOpen((current) => ({ ...current, [rowKey]: !open }))
                }
                className="flex h-7 w-full cursor-pointer items-center justify-start gap-2 rounded-none p-0 text-left font-normal hover:bg-transparent hover:text-inherit active:bg-transparent aria-expanded:bg-transparent aria-expanded:text-inherit focus-visible:ring-0 focus-visible:outline-none"
              >
                <span
                  className="flex size-3.5 shrink-0 items-center justify-center text-muted-foreground/60"
                  data-task-status={todo.status}
                  aria-hidden="true"
                >
                  {todo.status === "completed" ? (
                    <Check className="size-3.5 text-muted-foreground/70" strokeWidth={2.2} />
                  ) : todo.status === "in_progress" ? (
                    <LoaderCircle className="size-3.5 motion-safe:animate-spin text-muted-foreground/60" strokeWidth={2} />
                  ) : (
                    <span className="text-[11px] font-mono text-muted-foreground/50">{i + 1}</span>
                  )}
                </span>
                <span className="truncate text-[13px] font-medium text-muted-foreground/90">
                  {todo.content}
                </span>
                <span className="text-muted-foreground/30 select-none" aria-hidden="true">
                  |
                </span>
                <span className="min-w-0 flex-1 truncate text-[12px] text-muted-foreground/60 tabular-nums">
                  {statusLabel}
                </span>
                <ChevronsUpDown
                  className="size-3.5 shrink-0 text-muted-foreground/50 ml-auto"
                  aria-hidden="true"
                />
              </Button>

              <div
                className="grid transition-[grid-template-rows,opacity] duration-200 motion-reduce:transition-none"
                style={{
                  gridTemplateRows: open ? "1fr" : "0fr",
                  opacity: open ? 1 : 0,
                }}
              >
                <div className="overflow-hidden">
                  {open && (
                    <div className="ml-[6.5px] border-l border-muted-foreground/30 hover:border-muted-foreground/70 transition-colors duration-150 pl-3.5 my-1.5 w-full">
                      <pre className="m-0 w-full overflow-x-auto rounded-md bg-muted/50 border border-border/40 p-2 font-mono text-[11.5px] leading-5 text-foreground/85">
                        {JSON.stringify(todo, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
