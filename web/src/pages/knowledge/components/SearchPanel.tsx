import { useMemo, useState } from "react"
import { FileText, Search, Sparkles, X } from "lucide-react"

import { searchKnowledgeChunks } from "@/api/knowledge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Empty, EmptyDescription, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { useTranslation } from "@/i18n"
import type { KnowledgeChunkSearchResponse } from "@/api/knowledge"
import { ChunkCard } from "@/pages/knowledge/components/ChunkCard"
import { FileChunksDialog } from "@/pages/knowledge/components/FileChunksDialog"
import { groupChunksByFile } from "@/pages/knowledge/lib/chunks"

const clampTopK = (value: string) => {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return 8
  return Math.min(50, Math.max(1, Math.round(parsed)))
}

export function SearchPanel({
  kbId,
  onOpenFile
}: {
  kbId: string
  onOpenFile?: (fileId: string) => void
}) {
  const { t } = useTranslation()
  const [draft, setDraft] = useState("")
  const [topK, setTopK] = useState("8")
  const [minScore, setMinScore] = useState("")
  const [response, setResponse] = useState<KnowledgeChunkSearchResponse | null>(null)
  const [searchedQuery, setSearchedQuery] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [dialogFile, setDialogFile] = useState<{ id: string; name: string } | null>(null)

  const visibleHits = useMemo(() => {
    if (!response) return []
    const threshold = minScore.trim() === "" ? null : Number(minScore)
    return response.hits.filter((hit) => {
      if (threshold === null || !Number.isFinite(threshold)) return true
      return (hit.score ?? 0) >= threshold
    })
  }, [response, minScore])

  const groups = useMemo(() => groupChunksByFile(visibleHits), [visibleHits])
  const fileCount = groups.length

  async function runSearch(event?: React.FormEvent) {
    event?.preventDefault()
    const query = draft.trim()
    if (!query || loading) return
    const limit = clampTopK(topK)
    setTopK(String(limit))
    setLoading(true)
    setError("")
    try {
      const result = await searchKnowledgeChunks(kbId, query, limit)
      setResponse(result)
      setSearchedQuery(query)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("Request failed"))
    } finally {
      setLoading(false)
    }
  }

  function clearSearch() {
    setResponse(null)
    setSearchedQuery("")
    setError("")
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-border px-(--page-padding) py-3">
        <div className="flex items-center gap-2.5">
          <h2 className="text-sm font-medium">{t("Search chunks")}</h2>
          {response && (
            <Badge variant="secondary" className="rounded-md tabular-nums">
              {visibleHits.length}
            </Badge>
          )}
        </div>
        {response && (
          <Button variant="ghost" size="sm" onClick={clearSearch}>
            <X />{t("Clear results")}
          </Button>
        )}
      </div>
      <div className="grid min-h-0 flex-1 overflow-hidden lg:grid-cols-[320px_minmax(0,1fr)]">
        <form
          onSubmit={runSearch}
          className="flex min-h-0 flex-col gap-4 overflow-y-auto border-b border-border p-(--page-padding) lg:border-r lg:border-b-0"
        >
          <div>
            <h3 className="text-sm font-medium">{t("Search your collection")}</h3>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              {t("Search across indexed chunks. Results are grouped by document.")}
            </p>
          </div>
          <div className="grid gap-2">
            <label htmlFor="knowledge-search-query" className="text-xs font-medium">
              {t("Query")}
            </label>
            <Textarea
              id="knowledge-search-query"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={t("Describe what you are looking for…")}
              rows={3}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                  event.preventDefault()
                  void runSearch()
                }
              }}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <label htmlFor="knowledge-search-topk" className="text-xs font-medium">
                {t("Top K")}
              </label>
              <Input
                id="knowledge-search-topk"
                type="number"
                min={1}
                max={50}
                value={topK}
                onChange={(event) => setTopK(event.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <label htmlFor="knowledge-search-minscore" className="text-xs font-medium">
                {t("Minimum similarity")}
              </label>
              <Input
                id="knowledge-search-minscore"
                type="number"
                step="0.05"
                min={-1}
                max={1}
                value={minScore}
                placeholder="—"
                onChange={(event) => setMinScore(event.target.value)}
              />
            </div>
          </div>
          <p className="text-[11px] leading-4 text-muted-foreground">
            {t("Minimum similarity is applied in the browser to the returned chunks.")}
          </p>
          <Button type="submit" disabled={!draft.trim() || loading}>
            {loading ? <Spinner /> : <Search />}
            {loading ? t("Searching…") : t("Search collection")}
          </Button>
          {response && (
            <dl className="grid gap-2 rounded-lg border border-border bg-muted/30 p-3 text-[11px] text-muted-foreground">
              <div className="flex items-center justify-between gap-3">
                <dt>{t("Retriever")}</dt>
                <dd className="text-right text-foreground">
                  {response.rerank?.applied
                    ? t("Reranked by {{model}}", { model: response.rerank.model_spec })
                    : t("Vector search")}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt>{t("Embedding")}</dt>
                <dd className="max-w-40 truncate text-right text-foreground" title={response.embedding_model_spec}>
                  {response.embedding_model_spec} · {response.embedding_dimension}d
                </dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt>{t("Candidates")}</dt>
                <dd className="text-right text-foreground tabular-nums">
                  {response.rerank ? response.rerank.candidate_count : response.hits.length}
                </dd>
              </div>
            </dl>
          )}
        </form>

        <section className="min-h-0 overflow-y-auto p-(--page-padding)" aria-label={t("Search results")}>
          {loading ? (
            <div className="grid min-h-60 place-items-center text-muted-foreground" role="status" aria-label={t("Searching…")}>
              <Spinner className="size-6" />
            </div>
          ) : error ? (
            <Empty className="min-h-60">
              <EmptyMedia><Search /></EmptyMedia>
              <EmptyTitle>{t("Search failed")}</EmptyTitle>
              <EmptyDescription role="alert">{error}</EmptyDescription>
              <Button variant="outline" onClick={() => runSearch()}>{t("Retry")}</Button>
            </Empty>
          ) : !response ? (
            <Empty className="min-h-60">
              <EmptyMedia><Sparkles /></EmptyMedia>
              <EmptyTitle>{t("Search your collection")}</EmptyTitle>
              <EmptyDescription>
                {t("Enter a query to retrieve the most relevant indexed chunks.")}
              </EmptyDescription>
            </Empty>
          ) : !visibleHits.length ? (
            <Empty className="min-h-60">
              <EmptyMedia><Search /></EmptyMedia>
              <EmptyTitle>{t("No matching chunks")}</EmptyTitle>
              <EmptyDescription>
                {t("Try a different query or lower the minimum similarity.")}
              </EmptyDescription>
            </Empty>
          ) : (
            <div className="grid gap-4">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                <span>
                  {t("{{chunks}} chunks from {{files}} files", {
                    chunks: visibleHits.length,
                    files: fileCount
                  })}
                  {searchedQuery ? ` · “${searchedQuery}”` : ""}
                </span>
                <span className="tabular-nums">
                  {t("Top K")}: {response.hits.length}
                </span>
              </div>
              {groups.map((group) => (
                <section key={group.key} className="overflow-hidden rounded-xl border border-border bg-card/50">
                  <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-muted/35 px-3 py-2.5">
                    <div className="flex min-w-0 items-center gap-2">
                      <FileText className="size-4 shrink-0 text-primary" />
                      <span className="truncate text-xs font-medium" title={group.fileName}>
                        {group.fileName}
                      </span>
                      <Badge variant="outline" className="rounded-md text-[10px] font-normal">
                        {t("{{count}} chunks", { count: group.chunks.length })}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-1">
                      {onOpenFile && group.fileId && (
                        <Button variant="ghost" size="sm" onClick={() => onOpenFile(group.fileId)}>
                          {t("View document")}
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setDialogFile({ id: group.fileId, name: group.fileName })}
                      >
                        {t("View all chunks")}
                      </Button>
                    </div>
                  </header>
                  <div className="grid gap-2.5 p-3">
                    {group.chunks.map((chunk, index) => (
                      <ChunkCard key={chunk.chunk_id || `${group.key}-${index}`} chunk={chunk} position={index + 1} showSource={false} />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          )}
        </section>
      </div>
      <FileChunksDialog
        kbId={kbId}
        fileId={dialogFile?.id ?? null}
        fileName={dialogFile?.name}
        open={dialogFile !== null}
        onOpenChange={(open) => { if (!open) setDialogFile(null) }}
      />
    </div>
  )
}
