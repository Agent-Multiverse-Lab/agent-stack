import { useEffect, useId, useState } from "react"

import { getAgentContext } from "@/api/agent"
import { Badge } from "@/components/ui/badge"
import { Field, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { useTranslation } from "@/i18n"
import type { AgentContextConfiguration } from "@/types/chat"

export function AgentConfiguration({ agentId }: { agentId: string }) {
  const { t } = useTranslation()
  const id = useId()
  const [configuration, setConfiguration] = useState<AgentContextConfiguration | null>(null)
  const [error, setError] = useState("")

  useEffect(() => {
    const controller = new AbortController()
    setConfiguration(null)
    setError("")
    getAgentContext(agentId, controller.signal).then((result) => {
      if (!controller.signal.aborted) setConfiguration(result)
    }).catch((cause) => {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : t("Request failed"))
    })
    return () => controller.abort()
  }, [agentId, t])

  if (error) return <p role="alert" className="text-sm text-destructive">{error}</p>
  if (!configuration) return <p role="status" className="text-sm text-muted-foreground">{t("Loading...")}</p>

  const sectionClass = "space-y-3 border-t border-border pt-5"
  const textClass = "h-32 min-h-0 resize-none overflow-y-auto field-sizing-fixed"
  const empty = t("Not configured")

  return (
    <>
      <section className={sectionClass} aria-labelledby={`${id}-model-heading`}>
        <h3 id={`${id}-model-heading`} className="text-sm font-semibold">{t("Model and prompt")}</h3>
        <Field>
          <FieldLabel htmlFor={`${id}-model`}>{t("Agent model")}</FieldLabel>
          <Input id={`${id}-model`} value={configuration.model} readOnly placeholder={empty} />
        </Field>
        <Field>
          <FieldLabel htmlFor={`${id}-prompt`}>{t("System prompt")}</FieldLabel>
          <Textarea id={`${id}-prompt`} value={configuration.system_prompt} readOnly placeholder={empty} className={textClass} />
        </Field>
      </section>

      <section className={sectionClass} aria-labelledby={`${id}-summary-heading`}>
        <h3 id={`${id}-summary-heading`} className="text-sm font-semibold">{t("Context summarization")}</h3>
        <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-3 text-sm">
          <dt className="text-muted-foreground">{t("Summary threshold")}</dt>
          <dd>{configuration.summary_threshold} K tokens</dd>
          <dt className="text-muted-foreground">{t("Recent messages retained")}</dt>
          <dd>{configuration.summary_keep_messages}</dd>
          <dt className="text-muted-foreground">{t("Tool result token limit")}</dt>
          <dd>{configuration.summary_tool_result_token_limit} tokens</dd>
        </dl>
        <Field>
          <FieldLabel htmlFor={`${id}-summary`}>{t("Summary prompt")}</FieldLabel>
          <Textarea id={`${id}-summary`} value={configuration.summary_prompt} readOnly placeholder={t("Default summary prompt")} className={textClass} />
        </Field>
      </section>

      <section className={sectionClass} aria-labelledby={`${id}-tools-heading`}>
        <h3 id={`${id}-tools-heading`} className="text-sm font-semibold">{t("Tools and skills")}</h3>
        <div className="space-y-2">
          <p className="text-sm text-muted-foreground">{t("Configured tools")}</p>
          <div className="max-h-32 overflow-y-auto">
            {configuration.tools.length ? <pre className="whitespace-pre-wrap break-all text-xs">{JSON.stringify(configuration.tools, null, 2)}</pre> : <p className="text-sm">{empty}</p>}
          </div>
        </div>
        <Field>
          <FieldLabel htmlFor={`${id}-skills`}>{t("Skill directory")}</FieldLabel>
          <Input id={`${id}-skills`} value={configuration.skill_root ?? ""} readOnly placeholder={empty} />
        </Field>
        <div className="space-y-2">
          <p className="text-sm text-muted-foreground">{t("MCP servers")}</p>
          <div className="flex max-h-32 flex-wrap gap-1.5 overflow-y-auto">
            {configuration.mcps.length ? configuration.mcps.map((server, index) => <Badge key={`${server}-${index}`} variant="outline" className="h-auto max-w-full whitespace-normal break-all">{server}</Badge>) : <p className="text-sm">{t("All configured servers")}</p>}
          </div>
        </div>
      </section>

      <section className={sectionClass} aria-labelledby={`${id}-assets-heading`}>
        <h3 id={`${id}-assets-heading`} className="text-sm font-semibold">{t("Style assets")}</h3>
        <pre tabIndex={0} className="max-h-40 overflow-auto whitespace-pre-wrap break-all rounded-lg border border-input bg-card p-3 text-xs">
          {Object.keys(configuration.style_profolio).length ? JSON.stringify(configuration.style_profolio, null, 2) : empty}
        </pre>
      </section>
    </>
  )
}
