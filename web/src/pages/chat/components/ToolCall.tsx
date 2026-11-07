import { useState } from "react"
import { Check, ChevronsUpDown, LoaderCircle, Pause, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useTranslation } from "@/i18n"
import { cn } from "@/lib/utils"
import { toolLabels } from "@/pages/chat/tool-labels"
import type { ToolCallBlock, ToolExecutionStatus } from "@/pages/chat/types"

const formatValue = (value: unknown): string => {
  if (typeof value === "string") return value
  return JSON.stringify(value, null, 2) ?? String(value)
}

const statusLabels: Record<ToolExecutionStatus, string> = {
  pending: "In progress",
  running: "In progress",
  completed: "Completed",
  error: "Failed",
  cancelled: "Cancelled",
  interrupted: "Interrupted",
  stopped: "Stopped",
}

const isToolExecutionStatus = (value: string): value is ToolExecutionStatus =>
  Object.prototype.hasOwnProperty.call(statusLabels, value)

interface ToolCallProps {
  block?: ToolCallBlock
  event?: Record<string, unknown>
}

export function ToolCall({ block, event }: ToolCallProps) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)

  const rawStatus = block?.status ?? String(event?.status ?? "pending")
  const status: ToolExecutionStatus = isToolExecutionStatus(rawStatus)
    ? rawStatus
    : "pending"

  const rawName =
    block?.name ?? (typeof event?.name === "string" ? event.name : t("Tool"))
  const label = toolLabels.get(rawName)
  const name = label ? t(label) : rawName
  const statusLabel = t(statusLabels[status])

  const rawOutput = block?.output !== undefined ? block.output : event?.output
  const output =
    typeof rawOutput === "object" && rawOutput !== null && "content" in rawOutput
      ? (rawOutput as { content: unknown }).content
      : rawOutput

  const rawProgress =
    block?.progress !== undefined
      ? block.progress
      : Array.isArray(event?.output_deltas)
        ? event.output_deltas.map(formatValue).join("")
        : ""

  const error = block?.error ?? event?.error
  const args = block?.args !== undefined ? block.args : event?.args

  const sections = [
    { label: "Arguments", value: args },
    { label: "Progress", value: rawProgress || undefined },
    { label: "Output", value: output },
    { label: "Error", value: error },
  ].filter((item) => item.value !== undefined)

  const renderStatusIcon = () => {
    if (status === "completed") {
      return (
        <Check
          className="size-3.5 motion-safe:zoom-in-75 text-muted-foreground/70"
          strokeWidth={2.2}
          aria-hidden="true"
        />
      )
    }
    if (status === "error") {
      return (
        <X
          className="size-3.5 text-destructive/80"
          strokeWidth={2.2}
          aria-hidden="true"
        />
      )
    }
    if (
      status === "cancelled" ||
      status === "interrupted" ||
      status === "stopped"
    ) {
      return (
        <Pause
          className="size-3.5 text-warning/80"
          strokeWidth={2.2}
          aria-hidden="true"
        />
      )
    }
    return (
      <LoaderCircle
        className="size-3.5 motion-safe:animate-spin text-muted-foreground/60"
        strokeWidth={2}
        aria-hidden="true"
      />
    )
  }

  return (
    <div className="w-full min-w-0">
      <Button
        type="button"
        variant="ghost"
        aria-label={`${name} ${statusLabel}`}
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className="flex h-7 w-full cursor-pointer items-center justify-start gap-2 rounded-none p-0 text-left font-normal hover:bg-transparent hover:text-inherit active:bg-transparent aria-expanded:bg-transparent aria-expanded:text-inherit focus-visible:ring-0 focus-visible:outline-none"
      >
        <span
          className="flex size-3.5 shrink-0 items-center justify-center text-muted-foreground/60"
          data-tool-status-icon={status}
          aria-hidden="true"
        >
          {renderStatusIcon()}
        </span>
        <span className="truncate text-[13px] font-medium text-muted-foreground/90">
          {name}
        </span>
        <span className="text-muted-foreground/30 select-none" aria-hidden="true">
          |
        </span>
        <span
          className="min-w-0 flex-1 truncate text-[12px] text-muted-foreground/60"
          aria-live="polite"
          aria-atomic="true"
        >
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
          gridTemplateRows: open && sections.length > 0 ? "1fr" : "0fr",
          opacity: open && sections.length > 0 ? 1 : 0,
        }}
      >
        <div className="overflow-hidden">
          {open && sections.length > 0 && (
            <div className="ml-[6.5px] border-l border-muted-foreground/30 hover:border-muted-foreground/70 transition-colors duration-150 pl-3.5 my-1.5 flex w-full min-w-0 flex-col gap-2">
              {sections.map((item) => (
                <div key={item.label} className="w-full min-w-0">
                  <div className="mb-0.5 flex items-center justify-between">
                    <span className="text-[11.5px] font-medium text-muted-foreground/70">
                      {t(item.label)}
                    </span>
                  </div>
                  <pre
                    className={cn(
                      "m-0 max-h-60 w-full overflow-auto rounded-md bg-muted/50 border border-border/40 p-2 font-mono text-[11.5px] leading-5 whitespace-pre-wrap break-words tabular-nums text-foreground/85",
                      item.label === "Error" && "bg-destructive/10 text-destructive border-destructive/20",
                    )}
                  >
                    {formatValue(item.value)}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
