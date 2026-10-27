import { useCallback, useEffect, useState } from "react"
import { Link, useParams } from "react-router"
import { ArrowLeft, BookOpen, Copy, Files, MessagesSquare, Network, RefreshCw, Rows3, Search } from "lucide-react"
import { toast } from "sonner"

import { getKnowledgeBase, listKnowledgeFiles } from "@/api/knowledge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useTranslation } from "@/i18n"
import type { KnowledgeBase } from "@/api/knowledge"
import { ChatPanel } from "@/pages/knowledge/components/ChatPanel"
import { ChunksPanel } from "@/pages/knowledge/components/ChunksPanel"
import { FilesPanel } from "@/pages/knowledge/components/FilesPanel"
import { GraphPanel } from "@/pages/knowledge/components/GraphPanel"
import { SearchPanel } from "@/pages/knowledge/components/SearchPanel"
import { formatFileSize } from "@/pages/knowledge/lib/format"

interface CollectionStats {
  files: number
  indexed: number
  size: number
}

const INDEXED_STATUSES = new Set(["indexed", "extracted"])

export default function KnowledgeBaseDetailPage() {
  const { kbId } = useParams<{ kbId: string }>()
  const { t } = useTranslation()
  const [base, setBase] = useState<KnowledgeBase | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [reload, setReload] = useState(0)
  const [stats, setStats] = useState<CollectionStats | null>(null)
  const [statsReload, setStatsReload] = useState(0)
  const [activeTab, setActiveTab] = useState("documents")
  const [focusFileId, setFocusFileId] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    if (!kbId) return
    setLoading(true)
    setError("")
    getKnowledgeBase(kbId)
      .then((result) => { if (active) setBase(result) })
      .catch((caught: unknown) => { if (active) setError(caught instanceof Error ? caught.message : t("Request failed")) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [kbId, t, reload])

  useEffect(() => {
    if (!kbId) return
    let active = true
    listKnowledgeFiles(kbId)
      .then((items) => {
        if (!active) return
        setStats({
          files: items.length,
          indexed: items.filter((file) => INDEXED_STATUSES.has(file.status)).length,
          size: items.reduce((sum, file) => sum + file.file_size, 0)
        })
      })
      .catch(() => { if (active) setStats(null) })
    return () => { active = false }
  }, [kbId, statsReload])

  const handleOpenFile = useCallback((fileId: string) => {
    setFocusFileId(fileId)
    setActiveTab("documents")
  }, [])

  async function copyCollectionId() {
    if (!base) return
    try {
      await navigator.clipboard.writeText(base.kb_id)
      toast.success(t("Collection ID copied"))
    } catch {
      toast.error(t("Unable to copy collection ID"))
    }
  }

  if (kbId && loading) return <div className="grid h-full place-items-center text-muted-foreground" role="status" aria-label={t("Loading knowledge bases")}><Spinner className="size-6" /></div>
  if (!kbId || error || !base) return (
    <div className="grid h-full place-content-center justify-items-center gap-4 text-sm text-muted-foreground">
      <BookOpen className="size-8" strokeWidth={1.5} />
      <p role="alert">{error || t("Knowledge base not found")}</p>
      {kbId && <Button variant="outline" onClick={() => setReload((value) => value + 1)}>{t("Retry")}</Button>}
      <Link to="/knowledge" className="text-primary underline underline-offset-4">{t("Back to knowledge bases")}</Link>
    </div>
  )

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden bg-background text-foreground">
      <header className="shrink-0 border-b border-border bg-card px-(--page-padding)">
        <nav aria-label={t("Knowledge base navigation")} className="flex h-11 items-center gap-2 text-xs text-muted-foreground">
          <Link to="/knowledge" className="inline-flex items-center gap-1.5 rounded-sm transition-colors hover:text-foreground">
            <ArrowLeft className="size-3.5" />{t("Knowledge Bases")}
          </Link>
          <span aria-hidden="true" className="text-border">/</span>
          <span className="min-w-0 truncate text-foreground">{base.name}</span>
        </nav>
        <div className="flex flex-wrap items-start justify-between gap-4 pb-4">
          <div className="flex min-w-0 items-start gap-3">
            <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-selection text-selection-foreground">
              <BookOpen className="size-5" strokeWidth={1.5} />
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="min-w-0 truncate text-xl font-semibold tracking-tight">{base.name}</h1>
                <Badge variant={base.status === "active" ? "success" : "outline"} className="rounded-md font-normal">
                  {t(base.status)}
                </Badge>
                <Badge variant="outline" className="rounded-md font-normal">{t("Collection")}</Badge>
              </div>
              <p className="mt-1 max-w-3xl text-xs leading-5 text-muted-foreground">
                {base.description || t("No description")}
              </p>
              {stats && (
                <dl className="mt-2.5 flex flex-wrap items-center gap-x-5 gap-y-1 text-[11px] text-muted-foreground">
                  <div className="flex items-baseline gap-1.5">
                    <dt>{t("Files")}</dt>
                    <dd className="font-medium text-foreground tabular-nums">{stats.files}</dd>
                  </div>
                  <div className="flex items-baseline gap-1.5">
                    <dt>{t("Indexed")}</dt>
                    <dd className="font-medium text-foreground tabular-nums">{stats.indexed}</dd>
                  </div>
                  <div className="flex items-baseline gap-1.5">
                    <dt>{t("Total size")}</dt>
                    <dd className="font-medium text-foreground tabular-nums">{formatFileSize(stats.size)}</dd>
                  </div>
                </dl>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={copyCollectionId}>
              <Copy />{t("Copy ID")}
            </Button>
            <Button variant="ghost" size="icon-sm" aria-label={t("Refresh statistics")} title={t("Refresh statistics")} onClick={() => setStatsReload((value) => value + 1)}>
              <RefreshCw />
            </Button>
          </div>
        </div>
      </header>
      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(String(value))} key={kbId} className="min-h-0 flex-1 flex-col">
        <TabsList className="h-10 w-full shrink-0 justify-start gap-7 overflow-x-auto border-b border-border px-(--page-padding)">
          <TabsTrigger value="documents" className="h-10 border-b-2 border-transparent px-0 data-active:border-primary"><Files className="size-4" />{t("Documents")}</TabsTrigger>
          <TabsTrigger value="chunks" className="h-10 border-b-2 border-transparent px-0 data-active:border-primary"><Rows3 className="size-4" />{t("Chunks")}</TabsTrigger>
          <TabsTrigger value="search" className="h-10 border-b-2 border-transparent px-0 data-active:border-primary"><Search className="size-4" />{t("Search")}</TabsTrigger>
          <TabsTrigger value="graph" className="h-10 border-b-2 border-transparent px-0 data-active:border-primary"><Network className="size-4" />{t("Knowledge Graph")}</TabsTrigger>
          <TabsTrigger value="chat" className="h-10 border-b-2 border-transparent px-0 data-active:border-primary"><MessagesSquare className="size-4" />{t("Knowledge Chat")}</TabsTrigger>
        </TabsList>
        <TabsContent value="documents" className="min-h-0"><FilesPanel kbId={kbId} initialFileId={focusFileId} /></TabsContent>
        <TabsContent value="chunks" className="min-h-0"><ChunksPanel kbId={kbId} /></TabsContent>
        <TabsContent value="search" className="min-h-0"><SearchPanel kbId={kbId} onOpenFile={handleOpenFile} /></TabsContent>
        <TabsContent value="graph" className="min-h-0"><GraphPanel kbId={kbId} /></TabsContent>
        <TabsContent value="chat" className="min-h-0"><ChatPanel kbId={kbId} /></TabsContent>
      </Tabs>
    </div>
  )
}
