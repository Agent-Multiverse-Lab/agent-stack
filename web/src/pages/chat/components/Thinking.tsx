import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { ChevronDown, LoaderCircle } from "lucide-react";
import { useTranslation } from "@/i18n";

function ElapsedTime({ startedAt }: { startedAt: number }) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(timer);
  }, []);
  const seconds = Math.max(0, now - startedAt) / 1000;
  return (
    <span
      className="font-mono text-xs tabular-nums text-muted-foreground"
      aria-hidden="true"
    >
      {seconds < 60
        ? `${seconds.toFixed(1)}s`
        : `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(1)}s`}
    </span>
  );
}

export function Thinking({
  label = "Thinking",
  children,
  startedAt,
}: {
  label?: string;
  children?: ReactNode;
  startedAt?: number | null;
}) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(true);
  return (
    <Collapsible
      open={expanded}
      onOpenChange={setExpanded}
      className="w-full max-w-[38rem]"
    >
      <div
        className="flex w-fit items-center gap-2.5 py-1"
        role="status"
        aria-live="polite"
      >
        <LoaderCircle size={16} className="animate-spin text-muted-foreground" />
        <span className="text-[13px] font-medium">{t(label)}</span>
        {typeof startedAt === "number" && Number.isFinite(startedAt) && (
          <ElapsedTime key={startedAt} startedAt={startedAt} />
        )}
        {children && (
          <CollapsibleTrigger
            render={<Button variant="ghost" size="icon-sm" />}
            aria-label={
              expanded ? t("Collapse thinking details") : t("Expand thinking details")
            }
          >
            <ChevronDown size={16} />
          </CollapsibleTrigger>
        )}
      </div>
      {children && (
        <CollapsibleContent className="relative mt-1 ml-[5px] min-w-0 border-l border-border py-1 pl-5">
          {children}
        </CollapsibleContent>
      )}
    </Collapsible>
  );
}
