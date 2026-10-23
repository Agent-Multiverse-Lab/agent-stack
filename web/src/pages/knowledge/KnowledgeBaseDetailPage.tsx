import { useEffect, useState } from "react"
import { Link, useParams } from "react-router"
import { ArrowLeft, BookOpen, Files, MessagesSquare, Network } from "lucide-react"

import { getKnowledgeBase } from "@/api/knowledge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useTranslation } from "@/i18n"
import type { KnowledgeBase } from "@/api/knowledge"
import { ChatPanel } from "@/pages/knowledge/components/ChatPanel"
import { FilesPanel } from "@/pages/knowledge/components/FilesPanel"
import { GraphPanel } from "@/pages/knowledge/components/GraphPanel"

export default function KnowledgeBaseDetailPage() {
  const { kbId } = useParams<{ kbId: string }>()
  const { t } = useTranslation()
  const [base, setBase] = useState<KnowledgeBase | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [reload, setReload] = useState(0)

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
      <header className="flex h-12 shrink-0 items-center justify-between gap-4 border-b border-border bg-card px-(--page-padding)">
        <div className="flex min-w-0 items-center gap-3">
          <nav aria-label={t("Knowledge base navigation")} className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
            <Link to="/knowledge" className="inline-flex items-center gap-1.5 rounded-sm transition-colors hover:text-foreground"><ArrowLeft className="size-3.5" />{t("Knowledge Bases")}</Link>
          </nav>
          <span aria-hidden="true" className="text-border">/</span>
          <div className="flex min-w-0 items-center gap-2">
            <div className="grid size-6 shrink-0 place-items-center rounded-md bg-selection text-selection-foreground"><BookOpen className="size-3.5" strokeWidth={1.5} /></div>
            <h1 className="truncate text-sm font-semibold tracking-tight">{base.name}</h1>
            <Badge variant="outline" className="shrink-0 font-normal">{t("Collection")}</Badge>
          </div>
        </div>
        {base.description && <p className="hidden max-w-md truncate text-xs text-muted-foreground lg:block">{base.description}</p>}
      </header>
      <Tabs key={kbId} defaultValue="documents" className="min-h-0 flex-1 flex-col">
        <TabsList className="h-10 w-full shrink-0 justify-start gap-7 border-b border-border px-(--page-padding)">
          <TabsTrigger value="documents" className="h-10 border-b-2 border-transparent px-0 data-active:border-primary"><Files className="size-4" />{t("Documents")}</TabsTrigger>
          <TabsTrigger value="graph" className="h-10 border-b-2 border-transparent px-0 data-active:border-primary"><Network className="size-4" />{t("Knowledge Graph")}</TabsTrigger>
          <TabsTrigger value="chat" className="h-10 border-b-2 border-transparent px-0 data-active:border-primary"><MessagesSquare className="size-4" />{t("Knowledge Chat")}</TabsTrigger>
        </TabsList>
        <TabsContent value="documents" className="min-h-0"><FilesPanel kbId={kbId} /></TabsContent>
        <TabsContent value="graph" className="min-h-0"><GraphPanel kbId={kbId} /></TabsContent>
        <TabsContent value="chat" className="min-h-0"><ChatPanel kbId={kbId} /></TabsContent>
      </Tabs>
    </div>
  )
}
