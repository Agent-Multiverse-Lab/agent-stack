import { useEffect, useState } from "react"
import { Link, useParams } from "react-router"
import { ArrowLeft, Database } from "lucide-react"

import { getKnowledgeBase } from "@/api/knowledge"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useTranslation } from "@/i18n"
import type { KnowledgeBase } from "@/types/knowledge"
import { ChatPanel } from "@/pages/knowledge/components/ChatPanel"
import { FilesPanel } from "@/pages/knowledge/components/FilesPanel"
import { GraphPanel } from "@/pages/knowledge/components/GraphPanel"

export default function KnowledgeBaseDetailPage() {
  const { kbId } = useParams<{ kbId: string }>()
  const { t } = useTranslation()
  const [base, setBase] = useState<KnowledgeBase | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    let active = true
    if (!kbId) return
    getKnowledgeBase(kbId)
      .then((result) => {
        if (active) setBase(result)
      })
      .catch((caught: unknown) => {
        if (active)
          setError(
            caught instanceof Error ? caught.message : t("Request failed")
          )
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [kbId, t])

  if (!kbId) {
    return (
      <div className="grid h-full place-items-center text-sm text-muted-foreground">
        {t("Knowledge base not found")}
      </div>
    )
  }
  if (loading) {
    return (
      <div className="grid h-full place-items-center text-muted-foreground">
        <Spinner className="size-6" />
      </div>
    )
  }
  if (error || !base) {
    return (
      <div className="grid h-full place-items-center text-sm text-muted-foreground">
        {error}
        <Link to="/knowledge" className="mt-2 text-primary hover:underline">
          {t("Back to knowledge bases")}
        </Link>
      </div>
    )
  }

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-background font-sans text-foreground">
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border px-4">
        <Link
          to="/knowledge"
          className="grid size-8 place-items-center rounded-md text-muted-foreground hover:bg-accent"
          aria-label={t("Back to knowledge bases")}
        >
          <ArrowLeft size={16} />
        </Link>
        <Database size={16} className="text-muted-foreground" />
        <h1 className="min-w-0 truncate text-base font-semibold">
          {base.name}
        </h1>
      </header>

      <Tabs
        defaultValue="documents"
        className="min-h-0 flex-1 [grid-template-rows:auto_minmax(0,1fr)]"
      >
        <TabsList className="h-10 w-full justify-start gap-5 border-b px-4">
          <TabsTrigger
            value="documents"
            className="h-10 border-b-2 border-transparent px-0 data-active:border-foreground"
          >
            {t("Documents")}
          </TabsTrigger>
          <TabsTrigger
            value="graph"
            className="h-10 border-b-2 border-transparent px-0 data-active:border-foreground"
          >
            {t("Knowledge Graph")}
          </TabsTrigger>
          <TabsTrigger
            value="chat"
            className="h-10 border-b-2 border-transparent px-0 data-active:border-foreground"
          >
            {t("Knowledge Chat")}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="documents" className="min-h-0">
          <FilesPanel kbId={kbId} />
        </TabsContent>
        <TabsContent value="graph" className="min-h-0">
          <GraphPanel kbId={kbId} />
        </TabsContent>
        <TabsContent value="chat" className="min-h-0">
          <ChatPanel kbId={kbId} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
