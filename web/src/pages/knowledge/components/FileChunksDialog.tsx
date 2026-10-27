import { useEffect, useState } from "react"
import { FileText, Rows3 } from "lucide-react"

import { getKnowledgeFileChunks } from "@/api/knowledge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog"
import { Empty, EmptyDescription, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Spinner } from "@/components/ui/spinner"
import { useTranslation } from "@/i18n"
import type { KnowledgeChunk } from "@/api/knowledge"
import { ChunkCard } from "@/pages/knowledge/components/ChunkCard"

const PAGE_SIZE = 20

export function FileChunksDialog({
  kbId,
  fileId,
  fileName,
  open,
  onOpenChange
}: {
  kbId: string
  fileId: string | null
  fileName?: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  const [chunks, setChunks] = useState<KnowledgeChunk[]>([])
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    if (!open || !fileId) return
    let active = true
    setChunks([])
    setHasMore(false)
    setError("")
    setLoading(true)
    getKnowledgeFileChunks(kbId, fileId, PAGE_SIZE, 0)
      .then((result) => {
        if (!active) return
        setChunks(result.chunks)
        setHasMore(result.has_more)
      })
      .catch((caught: unknown) => {
        if (active) {
          setError(caught instanceof Error ? caught.message : t("Request failed"))
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [open, kbId, fileId, t])

  async function loadMore() {
    if (!fileId || loadingMore) return
    setLoadingMore(true)
    try {
      const result = await getKnowledgeFileChunks(kbId, fileId, PAGE_SIZE, chunks.length)
      setChunks((current) => [...current, ...result.chunks])
      setHasMore(result.has_more)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("Request failed"))
    } finally {
      setLoadingMore(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[85vh] max-w-3xl flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span className="grid size-8 shrink-0 place-items-center rounded-md border border-border bg-muted text-primary">
              <FileText className="size-4" />
            </span>
            <span className="min-w-0 truncate" title={fileName ?? undefined}>
              {fileName || t("Document chunks")}
            </span>
          </DialogTitle>
          <DialogDescription>
            {t("Indexed chunks of this document")} ·{" "}
            {t("{{count}} chunks loaded", { count: chunks.length })}
            {hasMore ? ` · ${t("More chunks available")}` : ""}
          </DialogDescription>
        </DialogHeader>
        <div className="-mx-1 min-h-48 flex-1 overflow-y-auto px-1">
          {loading ? (
            <div
              className="grid min-h-40 place-items-center text-muted-foreground"
              role="status"
              aria-label={t("Loading chunks")}
            >
              <Spinner className="size-5" />
            </div>
          ) : error ? (
            <Empty className="min-h-40">
              <EmptyMedia>
                <Rows3 />
              </EmptyMedia>
              <EmptyTitle>{t("Unable to load chunks")}</EmptyTitle>
              <EmptyDescription role="alert">{error}</EmptyDescription>
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                {t("Close")}
              </Button>
            </Empty>
          ) : chunks.length ? (
            <div className="grid gap-2.5 py-1">
              {chunks.map((chunk, index) => (
                <ChunkCard
                  key={chunk.chunk_id || `${chunk.chunk_index}-${index}`}
                  chunk={chunk}
                  position={index + 1}
                />
              ))}
              {hasMore && (
                <Button
                  type="button"
                  variant="outline"
                  className="mx-auto"
                  disabled={loadingMore}
                  onClick={loadMore}
                >
                  {loadingMore && <Spinner />}
                  {t("Load more chunks")}
                </Button>
              )}
            </div>
          ) : (
            <Empty className="min-h-40">
              <EmptyMedia>
                <Rows3 />
              </EmptyMedia>
              <EmptyTitle>{t("No chunks yet")}</EmptyTitle>
              <EmptyDescription>
                {t("Parse and index this document to build searchable chunks.")}
              </EmptyDescription>
            </Empty>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("Close")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
