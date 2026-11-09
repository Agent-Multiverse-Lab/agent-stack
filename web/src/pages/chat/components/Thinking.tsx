import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { useState, type ReactNode } from "react"
import { Atom, ChevronsUpDown } from "lucide-react"
import { useTranslation } from "@/i18n"
import { cn } from "@/lib/utils"

export function Thinking({
  label,
  meta,
  status,
  children,
  active = true,
  autoExpand = active,
}: {
  label?: string
  meta?: string
  status?: string
  children?: ReactNode
  active?: boolean
  autoExpand?: boolean
  startedAt?: number | null
  durationMs?: number | null
}) {
  const { t } = useTranslation()
  const [expansion, setExpansion] = useState<{ autoExpand: boolean; open: boolean } | null>(null)
  const expanded = expansion?.autoExpand === autoExpand ? expansion.open : autoExpand

  const resolvedLabel = label ?? "Thinking"

  const labelEl = (
    <span
      className={
        active
          ? "thinking-shimmer bg-clip-text text-[13px] font-medium text-transparent"
          : "text-[13px] font-medium text-muted-foreground/80"
      }
      style={
        active
          ? {
              backgroundImage:
                "linear-gradient(90deg, var(--muted-foreground) 35%, var(--foreground) 50%, var(--muted-foreground) 65%)",
              backgroundSize: "200% 100%",
              animation: "shimmer-text 1.4s linear infinite",
            }
          : undefined
      }
    >
      {t(resolvedLabel)}
    </span>
  )

  return (
    <Collapsible
      open={expanded}
      onOpenChange={(open) => setExpansion({ autoExpand, open })}
      className="w-full min-w-0"
    >
      {children ? (
        <CollapsibleTrigger
          aria-label={
            expanded
              ? t("Collapse thinking details")
              : t("Expand thinking details")
          }
          render={
            <Button
              type="button"
              variant="ghost"
              className="flex h-7 w-full cursor-pointer items-center justify-between gap-2 rounded-none p-0 text-left font-normal hover:bg-transparent hover:text-inherit active:bg-transparent aria-expanded:bg-transparent aria-expanded:text-inherit focus-visible:ring-0 focus-visible:outline-none"
            />
          }
        >
          <div
            className="flex min-w-0 items-center gap-2"
            role={active ? "status" : undefined}
            aria-live={active ? "polite" : undefined}
          >
            <Atom
              className={cn(
                "size-3.5 shrink-0 text-muted-foreground/70",
                active && "motion-safe:animate-spin motion-safe:[animation-duration:3s]",
              )}
              aria-hidden="true"
            />
            {labelEl}
            {meta && (
              <>
                <span className="text-muted-foreground/30" aria-hidden="true">·</span>
                <span className="truncate text-[12px] text-muted-foreground/60">
                  {meta}
                </span>
              </>
            )}
            {status && (
              <span className="shrink-0 text-[11px] text-muted-foreground/60">
                {status}
              </span>
            )}
          </div>
          <ChevronsUpDown
            className="size-3.5 shrink-0 text-muted-foreground/50 ml-auto"
            aria-hidden="true"
          />
        </CollapsibleTrigger>
      ) : (
        <div
          className="flex h-7 w-full items-center gap-2"
          role={active ? "status" : undefined}
          aria-live={active ? "polite" : undefined}
        >
          <Atom
            className={cn(
              "size-3.5 shrink-0 text-muted-foreground/70",
              active && "motion-safe:animate-spin motion-safe:[animation-duration:3s]",
            )}
            aria-hidden="true"
          />
          {labelEl}
          {meta && (
            <>
              <span className="text-muted-foreground/30" aria-hidden="true">·</span>
              <span className="truncate text-[12px] text-muted-foreground/60">
                {meta}
              </span>
            </>
          )}
          {status && (
            <span className="shrink-0 text-[11px] text-muted-foreground/60">
              {status}
            </span>
          )}
        </div>
      )}
      {children && (
        <CollapsibleContent className="relative mt-1 w-full min-w-0">
          {children}
        </CollapsibleContent>
      )}
    </Collapsible>
  )
}

export default Thinking
