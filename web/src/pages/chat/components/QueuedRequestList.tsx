import { useState } from "react";
import {
  ChevronDown,
  CornerDownRight,
  ListOrdered,
  Play,
  X,
} from "lucide-react";

import type { QueuedRunRequestItem } from "@/api/thread";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useTranslation } from "@/i18n";
import { cn } from "@/lib/utils";

/** 等待区排队请求列表组件属性。 */
export interface QueuedRequestListProps {
  requests: QueuedRunRequestItem[];
  isActive: boolean;
  hasPendingInteraction: boolean;
  isSubmitting: boolean;
  onSteer: (requestId: string) => void;
  onRemove: (requestId: string) => void;
}

/**
 * 展示当前会话的等待队列，支持折叠、转向、立即运行与移除操作。
 */
export function QueuedRequestList({
  requests,
  isActive,
  hasPendingInteraction,
  isSubmitting,
  onSteer,
  onRemove,
}: QueuedRequestListProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(true);

  if (requests.length === 0) return null;

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className="overflow-hidden rounded-xl border border-border bg-muted"
    >
      <CollapsibleTrigger
        aria-label={
          isOpen ? t("Collapse waiting requests") : t("Expand waiting requests")
        }
        render={
          <Button
            type="button"
            variant="ghost"
            className="flex h-8 w-full items-center justify-between gap-2 rounded-none px-3 text-xs font-medium text-muted-foreground hover:bg-accent/60 hover:text-foreground aria-expanded:bg-transparent aria-expanded:text-muted-foreground"
          />
        }
      >
        <span className="flex min-w-0 items-center gap-1.5">
          <ListOrdered className="size-3.5 shrink-0" aria-hidden="true" />
          <span className="truncate">{t("Waiting requests")}</span>
          <span className="inline-flex h-4 min-w-4 items-center justify-center rounded-sm bg-secondary px-1 text-[11px] font-medium text-secondary-foreground tabular-nums">
            {requests.length}
          </span>
        </span>
        <ChevronDown
          className={cn(
            "size-3.5 shrink-0 transition-transform duration-(--hover-transition-duration) motion-reduce:transition-none",
            !isOpen && "-rotate-90",
          )}
          aria-hidden="true"
        />
      </CollapsibleTrigger>

      <CollapsibleContent>
        <ul
          aria-label={t("Waiting requests")}
          className="m-0 grid max-h-44 list-none gap-0.5 overflow-y-auto border-t border-border p-1.5"
        >
          {requests.map((item, index) => {
            const isSteer = item.dispatch_policy === "steer";
            const label = item.content || t("Attachment");
            const canSteerOrRun =
              (!isActive || !isSteer) && !hasPendingInteraction;

            return (
              <li
                key={item.request_id}
                className="flex items-center gap-2 rounded-lg px-2 py-1 text-sm transition-colors duration-(--hover-transition-duration) hover:bg-card motion-reduce:transition-none"
              >
                <span
                  aria-hidden="true"
                  className="w-4 shrink-0 text-center text-[11px] text-muted-foreground/70 tabular-nums"
                >
                  {index + 1}
                </span>
                <Badge
                  variant={isSteer ? "default" : "secondary"}
                  className={cn(
                    "h-5 rounded-sm px-1.5 text-[11px] font-medium",
                    isSteer
                      ? "bg-selection text-selection-foreground"
                      : "text-muted-foreground",
                  )}
                >
                  {isSteer ? t("Steer") : t("Queued")}
                </Badge>
                <span
                  className="min-w-0 flex-1 truncate text-[13px] text-foreground"
                  title={label}
                >
                  {label}
                </span>
                <div className="flex shrink-0 items-center gap-1">
                  {canSteerOrRun && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="xs"
                      disabled={isSubmitting}
                      onClick={() => onSteer(item.request_id)}
                    >
                      {isActive ? (
                        <CornerDownRight
                          className="size-3"
                          aria-hidden="true"
                        />
                      ) : (
                        <Play className="size-3" aria-hidden="true" />
                      )}
                      {isActive ? t("Steer") : t("Run now")}
                    </Button>
                  )}
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-xs"
                    aria-label={t("Remove")}
                    title={t("Remove")}
                    onClick={() => onRemove(item.request_id)}
                    className="text-muted-foreground hover:bg-destructive-muted hover:text-destructive"
                  >
                    <X className="size-3.5" aria-hidden="true" />
                  </Button>
                </div>
              </li>
            );
          })}
        </ul>
      </CollapsibleContent>
    </Collapsible>
  );
}
