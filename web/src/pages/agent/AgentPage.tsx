import { useEffect, useState } from "react"
import { Bot, RefreshCw } from "lucide-react"

import { getAgentCatalog } from "@/api/agent"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Empty, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Spinner } from "@/components/ui/spinner"
import { useTranslation } from "@/i18n"
import { AgentCard } from "@/pages/agent/components/AgentCard"
import type { AgentCatalogEntry, AgentCatalogResponse } from "@/types/chat"

export default function AgentPage() {
  const { t } = useTranslation()
  const [catalog, setCatalog] = useState<AgentCatalogResponse>({ agents: [], subagents: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [refreshVersion, setRefreshVersion] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError("")
    void getAgentCatalog(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setCatalog(data)
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setError(caught instanceof Error ? caught.message : t("Request failed"))
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [refreshVersion, t])

  const leader = catalog.agents.find((agent) => agent.id === "LeaderAgent")
  const agents = catalog.agents.filter((agent) => agent.id !== "LeaderAgent")
  const hasAgents = catalog.agents.length + catalog.subagents.length > 0
  const refresh = () => setRefreshVersion((version) => version + 1)

  const handleAgentUpdated = (updated: AgentCatalogEntry) => {
    setCatalog((current) => ({
      agents: current.agents.map((agent) => agent.id === updated.id ? updated : agent),
      subagents: current.subagents.map((agent) => agent.id === updated.id ? updated : agent),
    }))
  }

  return (
    <main className="flex h-full min-h-0 w-full flex-col bg-background text-foreground" aria-label={t("Agent")}>
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-border px-(--page-padding)">
        <h1 className="text-[16px] font-semibold">{t("Agent")}</h1>
        <Button variant="ghost" size="icon" onClick={refresh} disabled={loading} aria-label={t("Refresh agents")}>
          <RefreshCw className="size-4" aria-hidden />
        </Button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-(--page-padding)">
        {loading ? (
          <div className="flex min-h-48 items-center justify-center gap-2 text-sm text-muted-foreground" role="status">
            <Spinner className="size-5" />
            {t("Loading...")}
          </div>
        ) : error ? (
          <div className="flex min-h-48 flex-col items-center justify-center gap-3 text-center" role="alert">
            <p className="text-sm font-medium">{t("Load failed")}</p>
            <p className="max-w-lg text-sm text-muted-foreground">{error}</p>
            <Button variant="outline" onClick={refresh}>{t("Retry")}</Button>
          </div>
        ) : !hasAgents ? (
          <Empty className="min-h-48">
            <EmptyMedia><Bot aria-hidden /></EmptyMedia>
            <EmptyTitle>{t("No agents yet")}</EmptyTitle>
          </Empty>
        ) : (
          <div className="space-y-8">
            {leader && (
              <section className="space-y-3" aria-labelledby="main-agent-heading">
                <h2 id="main-agent-heading" className="text-sm font-medium">{t("Main agent")}</h2>
                <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(280px,1fr))]">
                  <AgentCard agent={leader} onUpdated={handleAgentUpdated} />
                </div>
              </section>
            )}

            {agents.length > 0 && (
              <section className="space-y-3" aria-labelledby="agents-heading">
                <h2 id="agents-heading" className="flex items-center gap-2 text-sm font-medium">
                  {t("Agents")} <Badge>{agents.length}</Badge>
                </h2>
                <ul className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(280px,1fr))]">
                  {agents.map((agent) => <li key={agent.id}><AgentCard agent={agent} onUpdated={handleAgentUpdated} /></li>)}
                </ul>
              </section>
            )}

            <section className="space-y-3" aria-labelledby="subagents-heading">
              <h2 id="subagents-heading" className="flex items-center gap-2 text-sm font-medium">
                {t("Sub agents")} <Badge>{catalog.subagents.length}</Badge>
              </h2>
              {catalog.subagents.length > 0 ? (
                <ul className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(280px,1fr))]">
                  {catalog.subagents.map((agent) => <li key={agent.id}><AgentCard agent={agent} onUpdated={handleAgentUpdated} /></li>)}
                </ul>
              ) : (
                <p className="py-4 text-sm text-muted-foreground">{t("No subagents yet")}</p>
              )}
            </section>
          </div>
        )}
      </div>
    </main>
  )
}
