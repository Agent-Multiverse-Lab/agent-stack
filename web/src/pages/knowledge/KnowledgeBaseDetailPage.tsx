import { useCallback, useEffect, useState } from "react"
import { Link, useParams } from "react-router"
import { BookOpen, ClipboardList, Copy, Files, MessagesSquare, Network, Rows3, Search, Settings, ChartNoAxesCombined } from "lucide-react"

import { getKnowledgeBase, listKnowledgeFiles } from "@/api/knowledge"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useTranslation } from "@/i18n"
import type { KnowledgeBase } from "@/api/knowledge"
import { toast } from "sonner"
import { KnowledgeSettingsDialog } from "./components/KnowledgeSettingsDialog"
import { KnowledgeTasksPanel } from "./components/KnowledgeTasksPanel"
import { KnowledgeEvaluationPanel } from "./components/KnowledgeEvaluationPanel"
import { ChatPanel } from "@/pages/knowledge/components/ChatPanel"
import { ChunksPanel } from "@/pages/knowledge/components/ChunksPanel"
import { FilesPanel } from "@/pages/knowledge/components/FilesPanel"
import { GraphPanel } from "@/pages/knowledge/components/GraphPanel"
import { SearchPanel } from "@/pages/knowledge/components/SearchPanel"

export default function KnowledgeBaseDetailPage() {
  const { kbId } = useParams<{ kbId: string }>()
  const { t } = useTranslation()
  const [base, setBase] = useState<KnowledgeBase | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [reload, setReload] = useState(0)
  const [activeTab, setActiveTab] = useState("documents")
  const [settingsOpen, setSettingsOpen] = useState(false)
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
    listKnowledgeFiles(kbId).catch(() => {})
  }, [kbId])

  const handleOpenFile = useCallback((fileId: string) => {
    setFocusFileId(fileId)
    setActiveTab("documents")
  }, [])

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
      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(String(value))} key={kbId} className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <header className="flex h-12 shrink-0 items-center justify-between gap-4 border-b border-border bg-card px-4">
          <div className="flex min-w-0 flex-1 items-center">
            <nav aria-label={t("Knowledge base navigation")} className="flex min-w-0 items-center gap-2 text-sm font-medium">
              <Link to="/knowledge" className="shrink-0 text-muted-foreground transition-colors hover:text-foreground">
                {t("Knowledge Bases")}
              </Link>
              <span aria-hidden="true" className="text-muted-foreground/40">/</span>
              <h1 className="truncate text-sm font-medium text-foreground">{base.name}</h1>
            </nav>
          </div>
          <TabsList className="shrink-0 items-center gap-1.5 border-b-0 bg-transparent p-0">
            <TabsTrigger
              value="documents"
              className="h-8 rounded-full px-3.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground data-active:bg-accent data-active:text-foreground"
            >
              <Files className="size-3.5" />{t("Documents")}
            </TabsTrigger>
            <TabsTrigger
              value="chunks"
              className="h-8 rounded-full px-3.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground data-active:bg-accent data-active:text-foreground"
            >
              <Rows3 className="size-3.5" />{t("Chunks")}
            </TabsTrigger>
            <TabsTrigger
              value="search"
              className="h-8 rounded-full px-3.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground data-active:bg-accent data-active:text-foreground"
            >
              <Search className="size-3.5" />{t("Search")}
            </TabsTrigger>
            <TabsTrigger
              value="graph"
              className="h-8 rounded-full px-3.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground data-active:bg-accent data-active:text-foreground"
            >
              <Network className="size-3.5" />{t("Knowledge Graph")}
            </TabsTrigger>
            <TabsTrigger
              value="chat"
              className="h-8 rounded-full px-3.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground data-active:bg-accent data-active:text-foreground"
            >
              <MessagesSquare className="size-3.5" />{t("Knowledge Chat")}
            </TabsTrigger>
            <TabsTrigger value="evaluation"><ChartNoAxesCombined className="size-3.5" />评估</TabsTrigger>
            <TabsTrigger value="tasks"><ClipboardList className="size-3.5" />任务</TabsTrigger>
          </TabsList>
          <div className="flex min-w-0 flex-1 justify-end gap-1"><Button size="icon-sm" variant="ghost" aria-label="复制知识库 ID" onClick={() => { void navigator.clipboard.writeText(kbId).then(() => toast.success("ID 已复制")).catch(() => toast.error("复制失败")) }}><Copy /></Button><Button size="icon-sm" variant="ghost" aria-label="配置知识库" onClick={() => setSettingsOpen(true)}><Settings /></Button></div>
        </header>
        <TabsContent value="documents" className="min-h-0 flex-1"><FilesPanel kbId={kbId} initialFileId={focusFileId} /></TabsContent>
        <TabsContent value="chunks" className="min-h-0 flex-1"><ChunksPanel kbId={kbId} /></TabsContent>
        <TabsContent value="search" className="min-h-0 flex-1"><SearchPanel kbId={kbId} onOpenFile={handleOpenFile} /></TabsContent>
        <TabsContent value="graph" className="min-h-0 flex-1"><GraphPanel kbId={kbId} /></TabsContent>
        <TabsContent value="chat" className="min-h-0 flex-1"><ChatPanel kbId={kbId} /></TabsContent>
        <TabsContent value="evaluation" className="min-h-0 flex-1"><KnowledgeEvaluationPanel kbId={kbId} /></TabsContent>
        <TabsContent value="tasks" className="min-h-0 flex-1"><KnowledgeTasksPanel kbId={kbId} /></TabsContent>
      </Tabs>
      <KnowledgeSettingsDialog kbId={kbId} open={settingsOpen} onOpenChange={setSettingsOpen} onSaved={() => setReload(value => value + 1)} />
    </div>
  )
}
