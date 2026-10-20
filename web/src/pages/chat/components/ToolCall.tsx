import { Check, ChevronRight, CircleX, Clock3, LoaderCircle, Pause } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useTranslation } from "@/i18n";

const formatValue = (value: unknown) =>
  typeof value === "string" ? value : JSON.stringify(value, null, 2);

const statusLabels: Record<string, string> = {
  pending: "Pending",
  running: "In progress",
  completed: "Completed",
  error: "Failed",
  cancelled: "Cancelled",
  interrupted: "Interrupted",
  stopped: "Stopped",
};

export function ToolCall({ event }: { event: Record<string, unknown> }) {
  const { t } = useTranslation();
  const status = String(event.status ?? "pending");
  const name = typeof event.name === "string" ? event.name : t("Tool");
  const statusLabel = t(statusLabels[status] ?? "Pending");
  const Icon = status === "running" ? LoaderCircle
    : status === "completed" ? Check
      : status === "error" ? CircleX
        : status === "pending" ? Clock3 : Pause;
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
        <ChevronRight className="shrink-0 text-muted-foreground transition-transform group-data-open/tool:rotate-90" />
        <Icon className={status === "running"
          ? "shrink-0 animate-spin text-muted-foreground motion-reduce:animate-none"
          : status === "error" ? "shrink-0 text-destructive" : "shrink-0 text-muted-foreground"} />
        <span className="truncate font-medium">{name}</span>
        <span className="shrink-0 text-muted-foreground" aria-live="polite">
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
