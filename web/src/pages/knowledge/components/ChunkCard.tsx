import { useState } from "react"
import { FileText, Sparkles } from "lucide-react"

import { Button } from "@/components/ui/button"
import { useTranslation } from "@/i18n"
import { formatScore } from "@/pages/knowledge/lib/format"

export interface ChunkCardChunk {
  chunk_id?: string
  chunk_index: number
  content: string
  score?: number | null
  rerank_score?: number | null
  file_name?: string
}

export function ChunkCard({
  chunk,
  position,
  showSource = false
}: {
  chunk: ChunkCardChunk
  position: number
  showSource?: boolean
}) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)
  const content = chunk.content ?? ""
  const collapsible = content.length > 260 || content.split("\n").length > 5

  return (
    <article className="overflow-hidden rounded-lg border border-border bg-card">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-muted/35 px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="font-mono text-[11px] font-semibold text-primary tabular-nums">
            #{String(position).padStart(2, "0")}
          </span>
          {showSource && chunk.file_name && (
            <span className="flex min-w-0 items-center gap-1.5 text-[11px] text-muted-foreground">
              <FileText className="size-3 shrink-0" />
              <span className="truncate">{chunk.file_name}</span>
            </span>
          )}
          <span className="text-[11px] font-medium text-muted-foreground">
            {t("Chunk")} {chunk.chunk_index + 1}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
          {typeof chunk.score === "number" && (
            <span>
              {t("Similarity")}{" "}
              <b className="font-medium text-foreground tabular-nums">
                {formatScore(chunk.score)}
              </b>
            </span>
          )}
          {typeof chunk.rerank_score === "number" && (
            <span className="flex items-center gap-1">
              <Sparkles className="size-3" />
              {t("Rerank score")}{" "}
              <b className="font-medium text-foreground tabular-nums">
                {formatScore(chunk.rerank_score)}
              </b>
            </span>
          )}
        </div>
      </header>
      <div className="px-3 py-3">
        <p
          className={`break-words whitespace-pre-wrap text-[13px] leading-6 ${collapsible && !expanded ? "line-clamp-6" : ""}`}
        >
          {content || t("No chunk content")}
        </p>
        {collapsible && (
          <Button
            type="button"
            variant="link"
            size="sm"
            className="mt-2 h-auto p-0 text-xs"
            aria-expanded={expanded}
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? t("Collapse chunk") : t("Expand full chunk")}
          </Button>
        )}
      </div>
    </article>
  )
}
