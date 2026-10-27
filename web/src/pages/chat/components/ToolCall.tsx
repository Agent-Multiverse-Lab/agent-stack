import { useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { useTranslation } from "@/i18n";
import { cn } from "@/lib/utils";
import type { ToolExecutionStatus } from "@/pages/chat/types";

const formatValue = (value: unknown) => {
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2) ?? String(value);
};

export function TaskSpinnerRing({
  active = false,
  children,
}: {
  active?: boolean;
  children?: ReactNode;
}) {
  const size = 24;
  const stroke = 2;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <span className="relative inline-flex size-6 shrink-0 items-center justify-center">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className={cn(
          "size-6",
          active && "motion-safe:animate-spin motion-safe:[animation-duration:1s]",
        )}
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--border)"
          strokeWidth={stroke}
        />
        {active && (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="var(--primary)"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${c * 0.25} ${c * 0.75}`}
          />
        )}
      </svg>
      {children !== undefined && (
        <span className="absolute text-[10.5px] font-semibold tabular-nums text-foreground">
          {children}
        </span>
      )}
    </span>
  );
}

export function TaskStatusBadge({
  tone,
  children,
}: {
  tone: "green" | "red" | "amber";
  children: ReactNode;
}) {
  const toneClass =
    tone === "green"
      ? "bg-success text-white"
      : tone === "red"
        ? "bg-destructive text-white"
        : "bg-warning text-white";
  return (
    <span
      className={cn(
        "flex size-5.5 shrink-0 items-center justify-center rounded-full",
        toneClass,
      )}
    >
      {children}
    </span>
  );
}

export const TaskCheckIcon = (
  <svg
    width="13"
    height="13"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="3.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    className="size-[13px] motion-safe:zoom-in-75"
  >
    <path d="M20 6L9 17l-5-5" />
  </svg>
);

export const TaskXIcon = (
  <svg
    width="12"
    height="12"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="3.5"
    strokeLinecap="round"
    className="size-3"
  >
    <path d="M18 6L6 18M6 6l12 12" />
  </svg>
);

export const TaskPauseIcon = (
  <svg
    width="11"
    height="11"
    viewBox="0 0 24 24"
    fill="currentColor"
    className="size-[11px]"
  >
    <rect x="6" y="5" width="4" height="14" rx="1" />
    <rect x="14" y="5" width="4" height="14" rx="1" />
  </svg>
);

export function TaskChevron({ open }: { open: boolean }) {
  return (
    <span
      aria-hidden="true"
      className="-ml-1 flex size-7 shrink-0 items-center justify-center rounded-full text-muted-foreground"
    >
      <svg
        width="15"
        height="15"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="size-[15px] transition-transform duration-200 motion-reduce:transition-none"
        style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)" }}
      >
        <path d="M6 9l6 6 6-6" />
      </svg>
    </span>
  );
}

const statusLabels: Record<ToolExecutionStatus, string> = {
  pending: "In progress",
  running: "In progress",
  completed: "Completed",
  error: "Failed",
  cancelled: "Cancelled",
  interrupted: "Interrupted",
  stopped: "Stopped",
};

const isToolExecutionStatus = (value: string): value is ToolExecutionStatus =>
  Object.prototype.hasOwnProperty.call(statusLabels, value);

export function ToolCall({ event }: { event: Record<string, unknown> }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const receivedStatus = String(event.status ?? "pending");
  const status = isToolExecutionStatus(receivedStatus)
    ? receivedStatus
    : "pending";
  const name = typeof event.name === "string" ? event.name : t("Tool");
  const statusLabel = t(statusLabels[status]);
  const stepIndex =
    typeof event.index === "number" && Number.isFinite(event.index)
      ? event.index + 1
      : undefined;

  const output =
    typeof event.output === "object" &&
    event.output !== null &&
    "content" in event.output
      ? event.output.content
      : event.output;
  const progress = Array.isArray(event.output_deltas)
    ? event.output_deltas.map(formatValue).join("")
    : "";

  const sections = [
    { label: "Arguments", value: event.args },
    { label: "Progress", value: progress || undefined },
    { label: "Output", value: output },
    { label: "Error", value: event.error },
  ].filter((item) => item.value !== undefined);

  const renderBadge = () => {
    if (status === "completed") {
      return <TaskStatusBadge tone="green">{TaskCheckIcon}</TaskStatusBadge>;
    }
    if (status === "error") {
      return <TaskStatusBadge tone="red">{TaskXIcon}</TaskStatusBadge>;
    }
    if (
      status === "cancelled" ||
      status === "interrupted" ||
      status === "stopped"
    ) {
      return <TaskStatusBadge tone="amber">{TaskPauseIcon}</TaskStatusBadge>;
    }
    return <TaskSpinnerRing active>{stepIndex}</TaskSpinnerRing>;
  };

  const renderPill = () => {
    if (status === "completed") {
      return (
        <span className="inline-flex h-5.5 items-center gap-1.5 rounded-full border border-success-border bg-success-muted px-2 text-[11.5px] font-medium text-success">
          {statusLabel}
        </span>
      );
    }
    if (status === "error") {
      return (
        <span className="inline-flex h-5.5 items-center gap-1.5 rounded-full border border-destructive-border bg-destructive-muted px-2 text-[11.5px] font-medium text-destructive">
          {statusLabel}
        </span>
      );
    }
    if (
      status === "cancelled" ||
      status === "interrupted" ||
      status === "stopped"
    ) {
      return (
        <span className="inline-flex h-5.5 items-center gap-1.5 rounded-full border border-warning-border bg-warning-muted px-2 text-[11.5px] font-medium text-warning">
          {statusLabel}
        </span>
      );
    }
    return (
      <span className="text-[12px] text-muted-foreground">{statusLabel}</span>
    );
  };

  return (
    <div
      className="w-full max-w-2xl min-w-0 self-stretch overflow-hidden border border-border bg-card text-card-foreground shadow-sm transition-[border-radius,background-color] duration-200 hover:bg-accent/50"
      style={{ borderRadius: open ? 14 : 22 }}
    >
      <Button
        type="button"
        variant="ghost"
        aria-label={`${name} ${statusLabel}`}
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className="flex h-11 w-full items-center justify-start gap-2.5 rounded-none px-2.5 py-0 text-left font-normal hover:bg-transparent"
      >
        <span
          className="flex size-6 shrink-0 items-center justify-center"
          data-tool-status-icon={status}
          aria-hidden="true"
        >
          {renderBadge()}
        </span>
        <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-foreground">
          {name}
        </span>
        <span
          className="shrink-0"
          aria-live="polite"
          aria-atomic="true"
        >
          {renderPill()}
        </span>
        <TaskChevron open={open} />
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
            <div className="mb-2.5 grid grid-cols-[24px_minmax(0,1fr)] gap-2.5 px-2.5 pt-0.5">
              <span aria-hidden="true" className="mx-auto h-full w-px bg-border" />
              <div className="flex min-w-0 flex-col gap-2.5">
                {sections.map((item) => (
                  <div key={item.label} className="min-w-0">
                    <div className="mb-1 flex items-center justify-between">
                      <span className="text-[12px] font-medium text-muted-foreground">
                        {t(item.label)}
                      </span>
                    </div>
                    <pre
                      className={cn(
                        "m-0 max-h-60 overflow-auto rounded-md border border-border bg-muted/50 px-2.5 py-1.5 font-mono text-[11.5px] leading-5 whitespace-pre-wrap break-words tabular-nums",
                        item.label === "Error"
                          ? "border-destructive-border bg-destructive-muted/40 text-destructive"
                          : "text-muted-foreground",
                      )}
                    >
                      {formatValue(item.value)}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
