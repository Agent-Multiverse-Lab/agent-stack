import { useEffect, useState } from "react"
import { FileText, RefreshCw, Rows3 } from "lucide-react"

import { getKnowledgeFileChunks, listKnowledgeFiles } from "@/api/knowledge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Empty, EmptyDescription, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Spinner } from "@/components/ui/spinner"
import { useTranslation } from "@/i18n"
import type { KnowledgeChunk, KnowledgeFile, KnowledgeFileStatus } from "@/api/knowledge"
import { ChunkCard } from "@/pages/knowledge/components/ChunkCard"
import { formatFileSize } from "@/pages/knowledge/lib/format"

const PAGE_SIZE = 20
const PROCESSING: KnowledgeFileStatus[] = ["parsing", "indexing", "extracting"]
const INDEXED: KnowledgeFileStatus[] = ["indexed", "extracted"]

function statusLabel(status: KnowledgeFileStatus) {
  return status.charAt(0).toUpperCase() + status.slice(1)
}

export function ChunksPanel({ kbId }: { kbId: string }) {
  const { t } = useTranslation()
  const [files, setFiles] = useState<KnowledgeFile[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [chunks, setChunks] = useState<KnowledgeChunk[]>([])
  const [hasMore, setHasMore] = useState(false)
  const [loadingFiles, setLoadingFiles] = useState(true)
  const [loadingChunks, setLoadingChunks] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState("")
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let active = true
    setLoadingFiles(true)
    setError("")
    listKnowledgeFiles(kbId)
      .then((items) => {
        if (!active) return
        setFiles(items)
        setSelectedId((current) =>
          items.some((file) => file.file_id === current)
            ? current
            : (items.find((file) => INDEXED.includes(file.status)) ?? items[0])?.file_id ?? null
        )
      })
      .catch((caught: unknown) => {
        if (active) setError(caught instanceof Error ? caught.message : t("Request failed"))
      })
      .finally(() => {
        if (active) setLoadingFiles(false)
      })
    return () => {
      active = false
    }
  }, [kbId, reload, t])

  useEffect(() => {
    if (!selectedId) {
      setChunks([])
      setHasMore(false)
      return
    }
    let active = true
    setChunks([])
    setHasMore(false)
    setLoadingChunks(true)
    getKnowledgeFileChunks(kbId, selectedId, PAGE_SIZE, 0)
      .then((result) => {
        if (!active) return
        setChunks(result.chunks)
        setHasMore(result.has_more)
      })
      .catch((caught: unknown) => {
        if (active) setError(caught instanceof Error ? caught.message : t("Request failed"))
      })
      .finally(() => {
        if (active) setLoadingChunks(false)
      })
    return () => {
      active = false
    }
  }, [kbId, selectedId, t])

  async function loadMore() {
    if (!selectedId || loadingMore) return
    setLoadingMore(true)
    try {
      const result = await getKnowledgeFileChunks(kbId, selectedId, PAGE_SIZE, chunks.length)
      setChunks((current) => [...current, ...result.chunks])
      setHasMore(result.has_more)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("Request failed"))
    } finally {
      setLoadingMore(false)
    }
  }

  const selected = files.find((file) => file.file_id === selectedId) ?? null
  const indexed = selected ? INDEXED.includes(selected.status) : false

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-border px-(--page-padding) py-3">
        <div className="flex items-center gap-2.5">
          <h2 className="text-sm font-medium">{t("Browse chunks")}</h2>
          {!loadingFiles && <Badge variant="secondary" className="rounded-md tabular-nums">{files.length}</Badge>}
        </div>
        <Button variant="ghost" size="sm" onClick={() => setReload((value) => value + 1)}>
          <RefreshCw />{t("Refresh files")}
        </Button>
      </div>
      {error && (
        <div role="alert" className="flex items-center justify-between gap-3 border-b border-border px-4 py-2 text-xs text-destructive">
          <span>{error}</span>
          <Button variant="ghost" size="sm" onClick={() => setReload((value) => value + 1)}>{t("Retry")}</Button>
        </div>
      )}
      {loadingFiles ? (
        <div className="grid flex-1 place-items-center text-muted-foreground" role="status" aria-label={t("Loading files")}>
          <Spinner className="size-6" />
        </div>
      ) : !files.length ? (
        <Empty className="m-(--page-padding) flex-1">
          <EmptyMedia><Rows3 /></EmptyMedia>
          <EmptyTitle>{t("No documents yet")}</EmptyTitle>
          <EmptyDescription>{t("Upload documents and build their index to inspect chunks here.")}</EmptyDescription>
        </Empty>
      ) : (
        <div className="grid min-h-0 flex-1 overflow-hidden lg:grid-cols-[300px_minmax(0,1fr)]">
          <aside className="min-h-0 overflow-y-auto border-b border-border lg:border-r lg:border-b-0" aria-label={t("Documents")}>
            <ul className="divide-y divide-border">
              {files.map((file) => (
                <li key={file.file_id}>
                  <button
                    type="button"
                    className={`flex w-full min-w-0 items-start gap-2.5 px-3 py-3 text-left transition-colors hover:bg-accent/50 ${file.file_id === selectedId ? "bg-selection/60" : ""}`}
                    aria-pressed={file.file_id === selectedId}
                    onClick={() => setSelectedId(file.file_id)}
                  >
                    <span className="grid size-8 shrink-0 place-items-center rounded-md border border-border bg-card text-primary">
                      <FileText className="size-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-xs font-medium" title={file.original_file_name}>
                        {file.original_file_name}
                      </span>
                      <span className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground">
                        <Badge
                          variant={file.status === "failed" ? "destructive" : INDEXED.includes(file.status) ? "success" : "outline"}
                          className="h-4 rounded px-1 text-[9px] font-normal"
                        >
                          {PROCESSING.includes(file.status) ? t("Processing") : t(statusLabel(file.status))}
                        </Badge>
                        <span>{formatFileSize(file.file_size)}</span>
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </aside>
          <section className="min-h-0 overflow-y-auto p-(--page-padding)" aria-label={t("Document chunks")}>
            {!selected ? (
              <Empty className="min-h-60">
                <EmptyMedia><Rows3 /></EmptyMedia>
                <EmptyTitle>{t("Select a document to inspect its chunks")}</EmptyTitle>
              </Empty>
            ) : loadingChunks ? (
              <div className="grid min-h-60 place-items-center text-muted-foreground" role="status" aria-label={t("Loading chunks")}>
                <Spinner className="size-6" />
              </div>
            ) : !indexed && !chunks.length ? (
              <Empty className="min-h-60">
                <EmptyMedia><Rows3 /></EmptyMedia>
                <EmptyTitle>{t("No indexed chunks")}</EmptyTitle>
                <EmptyDescription>{t("This document has not been indexed yet. Parse and index it first.")}</EmptyDescription>
              </Empty>
            ) : !chunks.length ? (
              <Empty className="min-h-60">
                <EmptyMedia><Rows3 /></EmptyMedia>
                <EmptyTitle>{t("No chunks yet")}</EmptyTitle>
                <EmptyDescription>{t("No chunks were returned for this document.")}</EmptyDescription>
              </Empty>
            ) : (
              <div className="grid gap-3">
                <header className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <h3 className="truncate text-sm font-medium" title={selected.original_file_name}>{selected.original_file_name}</h3>
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      {t("{{count}} chunks loaded", { count: chunks.length })}
                      {hasMore ? ` · ${t("More chunks available")}` : ""}
                    </p>
                  </div>
                  <Badge variant="outline" className="rounded-md font-normal">
                    {t("{{count}} chunks", { count: chunks.length })}
                  </Badge>
                </header>
                {chunks.map((chunk, index) => (
                  <ChunkCard key={chunk.chunk_id || `${chunk.chunk_index}-${index}`} chunk={chunk} position={index + 1} />
                ))}
                {hasMore && (
                  <Button variant="outline" className="mx-auto" disabled={loadingMore} onClick={loadMore}>
                    {loadingMore && <Spinner />}
                    {t("Load more chunks")}
                  </Button>
                )}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
