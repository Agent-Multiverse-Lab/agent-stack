import {
  ChevronRight,
  CircleCheck,
  CircleX,
  Clock3,
  LoaderCircle,
  Pause,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useTranslation } from "@/i18n";
import { cn } from "@/lib/utils";
import type { ToolExecutionStatus } from "@/pages/chat/types";

const formatValue = (value: unknown) => {
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2) ?? String(value);
};

const statusView = {
  pending: {
    label: "Pending",
    icon: Clock3,
    className: "text-muted-foreground",
  },
  running: {
    label: "In progress",
    icon: LoaderCircle,
    className:
      "text-primary motion-safe:animate-spin motion-safe:[animation-duration:900ms]",
  },
  completed: {
    label: "Completed",
    icon: CircleCheck,
    className:
      "text-success motion-safe:animate-in motion-safe:fade-in motion-safe:zoom-in-75 motion-safe:duration-200",
  },
  error: {
    label: "Failed",
    icon: CircleX,
    className:
      "text-destructive motion-safe:animate-in motion-safe:fade-in motion-safe:spin-in-12 motion-safe:duration-200",
  },
  cancelled: {
    label: "Cancelled",
    icon: Pause,
    className: "text-warning",
  },
  interrupted: {
    label: "Interrupted",
    icon: Pause,
    className: "text-warning",
  },
  stopped: {
    label: "Stopped",
    icon: Pause,
    className: "text-warning",
  },
} satisfies Record<
  ToolExecutionStatus,
  { label: string; icon: typeof Clock3; className: string }
>;

const isToolExecutionStatus = (value: string): value is ToolExecutionStatus =>
  Object.prototype.hasOwnProperty.call(statusView, value);

export function ToolCall({ event }: { event: Record<string, unknown> }) {
  const { t } = useTranslation();
  const receivedStatus = String(event.status ?? "pending");
  const status = isToolExecutionStatus(receivedStatus)
    ? receivedStatus
    : "pending";
  const name = typeof event.name === "string" ? event.name : t("Tool");
  const view = statusView[status];
  const statusLabel = t(view.label);
  const Icon = view.icon;
  const output = typeof event.output === "object" && event.output !== null && "content" in event.output
    ? event.output.content : event.output;
  const progress = Array.isArray(event.output_deltas)
    ? event.output_deltas.map(formatValue).join("") : "";

  return (
    <Collapsible className="group/tool w-full max-w-2xl min-w-0 text-sm">
      <CollapsibleTrigger
        aria-label={`${name} ${statusLabel}`}
        render={
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-auto max-w-full justify-start px-1 py-1 text-xs"
          />
        }
      >
        <ChevronRight className="shrink-0 text-muted-foreground transition-transform group-data-open/tool:rotate-90 motion-reduce:transition-none" />
        <span
          className="grid size-4 shrink-0 place-items-center"
          data-tool-status-icon={status}
          aria-hidden="true"
        >
          <Icon key={status} className={cn("size-4", view.className)} />
        </span>
        <span className="truncate font-medium">{name}</span>
        <span
          className="shrink-0 text-muted-foreground"
          aria-live="polite"
          aria-atomic="true"
        >
          {statusLabel}
        </span>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-1.5 ml-3 grid min-w-0 gap-3 border-l border-border py-1 pl-3">
        {[
          { label: "Arguments", value: event.args },
          { label: "Progress", value: progress || undefined },
          { label: "Output", value: output },
          { label: "Error", value: event.error },
        ].filter((item) => item.value !== undefined).map((item) => (
          <div key={item.label} className="min-w-0">
            <p className="mb-1 text-xs font-medium text-muted-foreground">{t(item.label)}</p>
            <pre className={`m-0 max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs leading-5 ${item.label === "Error" ? "text-destructive" : "text-muted-foreground"}`}>
              {formatValue(item.value)}
            </pre>
          </div>
        ))}
      </CollapsibleContent>
    </Collapsible>
  );
}
