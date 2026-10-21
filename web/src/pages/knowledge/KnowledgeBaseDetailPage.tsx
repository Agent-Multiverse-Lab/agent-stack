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
    <div className="flex h-full min-w-0 flex-col overflow-hidden bg-background text-foreground">
      <header className="shrink-0 px-6 pt-6 lg:px-10">
        <nav aria-label={t("Knowledge base navigation")} className="mb-6 flex items-center gap-2 text-xs text-muted-foreground">
          <Link to="/knowledge" className="inline-flex items-center gap-2 rounded-sm transition-colors hover:text-foreground"><ArrowLeft className="size-3.5" />{t("Knowledge Bases")}</Link>
        </nav>
        <div className="mb-7 flex items-start gap-4">
          <div className="grid size-14 shrink-0 place-items-center rounded-xl bg-selection text-selection-foreground"><BookOpen className="size-7" strokeWidth={1.4} /></div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-3"><h1 className="truncate text-2xl font-semibold tracking-tight lg:text-[28px]">{base.name}</h1><Badge variant="outline" className="font-normal">{t("Collection")}</Badge></div>
            {base.description && <p className="mt-1.5 line-clamp-2 max-w-3xl text-sm leading-6 text-muted-foreground">{base.description}</p>}
          </div>
        </div>
      </header>
      <Tabs key={kbId} defaultValue="documents" className="min-h-0 flex-1 flex-col">
        <TabsList className="h-12 w-full shrink-0 justify-start gap-7 border-b border-border px-6 lg:px-10">
          <TabsTrigger value="documents" className="h-12 border-b-2 border-transparent px-0 data-active:border-primary"><Files className="size-4" />{t("Documents")}</TabsTrigger>
          <TabsTrigger value="graph" className="h-12 border-b-2 border-transparent px-0 data-active:border-primary"><Network className="size-4" />{t("Knowledge Graph")}</TabsTrigger>
          <TabsTrigger value="chat" className="h-12 border-b-2 border-transparent px-0 data-active:border-primary"><MessagesSquare className="size-4" />{t("Knowledge Chat")}</TabsTrigger>
        </TabsList>
        <TabsContent value="documents" className="min-h-0"><FilesPanel kbId={kbId} /></TabsContent>
        <TabsContent value="graph" className="min-h-0"><GraphPanel kbId={kbId} /></TabsContent>
        <TabsContent value="chat" className="min-h-0"><ChatPanel kbId={kbId} /></TabsContent>
      </Tabs>
    </div>
  )
}
