import { useEffect, useState } from "react"
import { Bot, RefreshCw } from "lucide-react"

import { listAgents } from "@/api/agent"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Empty, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Spinner } from "@/components/ui/spinner"
import { useTranslation } from "@/i18n"
import { AgentCard } from "@/pages/agent/components/AgentCard"
import { ModelProviderCards } from "@/pages/agent/components/ModelProviderCards"
import type { Agent } from "@/types/agent"

type AgentPageTab = "agents" | "models"
const CARD_GRID_CLASS = "grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(min(100%,320px),1fr))]"

export default function AgentPage() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState<AgentPageTab>("agents")
  const [allAgents, setAllAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [refreshVersion, setRefreshVersion] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError("")
    void listAgents(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setAllAgents(data)
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

  const leader = allAgents.find((agent) => !agent.is_subagent && agent.id === "LeaderAgent")
  const agents = allAgents.filter((agent) => !agent.is_subagent && agent.id !== "LeaderAgent")
  const subagents = allAgents.filter((agent) => agent.is_subagent)
  const hasAgents = allAgents.length > 0
  const refresh = () => setRefreshVersion((version) => version + 1)

  const handleAgentUpdated = (updated: Agent) => {
    setAllAgents((current) =>
      current.map((agent) => (agent.id === updated.id ? updated : agent))
    )
  }

  return (
    <main className="flex h-full min-h-0 w-full min-w-0 flex-col overflow-hidden bg-background text-foreground" aria-label={t("Agent")}>
      <header className="flex h-12 shrink-0 items-center justify-between gap-4 border-b border-border bg-card px-[14px] sm:px-(--page-padding)">
        <div className="flex min-w-0 items-center gap-3">
          <h1 className="truncate text-sm font-medium">{t("Agent")}</h1>
          <div className="flex items-center gap-1" role="group" aria-label={t("Agent")}>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              aria-pressed={activeTab === "agents"}
              className={
                activeTab === "agents"
                  ? "h-7 rounded-md bg-selection px-2.5 text-xs font-medium text-selection-foreground hover:bg-selection hover:text-selection-foreground"
                  : "h-7 rounded-md px-2.5 text-xs text-muted-foreground hover:text-foreground"
              }
              onClick={() => setActiveTab("agents")}
            >
              {t("Agents")}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              aria-pressed={activeTab === "models"}
              className={
                activeTab === "models"
                  ? "h-7 rounded-md bg-selection px-2.5 text-xs font-medium text-selection-foreground hover:bg-selection hover:text-selection-foreground"
                  : "h-7 rounded-md px-2.5 text-xs text-muted-foreground hover:text-foreground"
              }
              onClick={() => setActiveTab("models")}
            >
              {t("Models")}
            </Button>
          </div>
        </div>
        {activeTab === "agents" && (
          <Button variant="ghost" size="icon-sm" className="rounded-md" onClick={refresh} disabled={loading} aria-label={t("Refresh agents")}>
            <RefreshCw className={loading ? "size-4 animate-spin motion-reduce:animate-none" : "size-4"} aria-hidden />
          </Button>
        )}
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-[14px] py-(--page-padding) sm:px-(--page-padding)">
        {activeTab === "models" ? (
          <ModelProviderCards />
        ) : loading ? (
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
          <div className="space-y-6">
            {leader && (
              <section className="space-y-3" aria-labelledby="main-agent-heading">
                <h2 id="main-agent-heading" className="text-sm font-medium">{t("Main agent")}</h2>
                <div className={CARD_GRID_CLASS}>
                  <AgentCard agent={leader} onUpdated={handleAgentUpdated} />
                </div>
              </section>
            )}

            {agents.length > 0 && (
              <section className="space-y-3" aria-labelledby="agents-heading">
                <h2 id="agents-heading" className="flex items-center gap-2 text-sm font-medium">
                  {t("Agents")} <Badge>{agents.length}</Badge>
                </h2>
                <ul className={CARD_GRID_CLASS}>
                  {agents.map((agent) => <li key={agent.id}><AgentCard agent={agent} onUpdated={handleAgentUpdated} /></li>)}
                </ul>
              </section>
            )}

            <section className="space-y-3" aria-labelledby="subagents-heading">
              <h2 id="subagents-heading" className="flex items-center gap-2 text-sm font-medium">
                {t("Sub agents")} <Badge>{subagents.length}</Badge>
              </h2>
              {subagents.length > 0 ? (
                <ul className={CARD_GRID_CLASS}>
                  {subagents.map((agent) => <li key={agent.id}><AgentCard agent={agent} onUpdated={handleAgentUpdated} /></li>)}
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
