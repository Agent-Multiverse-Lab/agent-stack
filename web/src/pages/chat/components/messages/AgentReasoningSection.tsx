import { Brain, ChevronsUpDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { useTranslation } from "@/i18n"

interface AgentReasoningSectionProps {
  content: string
}

export function AgentReasoningSection({ content }: AgentReasoningSectionProps) {
  const { t } = useTranslation()
  if (!content) return null

  const preview = content.trim().split(/\r?\n/).at(-1) ?? ""

  return (
    <Collapsible className="group/reasoning w-full min-w-0 text-sm">
      <CollapsibleTrigger
        aria-label={`${t("Reasoning")} ${preview}`}
        render={
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="flex h-7 w-full cursor-pointer items-center justify-start gap-2 rounded-none p-0 text-left hover:bg-transparent hover:text-inherit active:bg-transparent aria-expanded:bg-transparent aria-expanded:text-inherit focus-visible:ring-0 focus-visible:outline-none"
          />
        }
      >
        <span
          className="flex size-3.5 shrink-0 items-center justify-center text-muted-foreground/60"
          aria-hidden="true"
        >
          <Brain className="size-3.5" />
        </span>
        <span className="shrink-0 text-[13px] font-medium text-muted-foreground/90">
          {t("Reasoning")}
        </span>
        {preview && (
          <>
            <span className="text-muted-foreground/30 select-none" aria-hidden="true">
              |
            </span>
            <span className="min-w-0 flex-1 truncate text-[12px] text-muted-foreground/60">
              {preview}
            </span>
          </>
        )}
        <ChevronsUpDown
          className="size-3.5 shrink-0 text-muted-foreground/50 ml-auto"
          aria-hidden="true"
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="ml-[6.5px] border-l border-muted-foreground/30 hover:border-muted-foreground/70 transition-colors duration-150 pl-3.5 mt-1 w-full max-h-72 overflow-auto whitespace-pre-wrap break-words py-1 text-xs leading-5 text-muted-foreground/80">
        {content}
      </CollapsibleContent>
    </Collapsible>
  )
}
