import { useId, useRef, useState } from "react"
import type { FormEvent } from "react"
import { ArrowRight, Bot, Network, Save, X } from "lucide-react"
import { toast } from "sonner"

import { updateAgent } from "@/api/agent"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Field, FieldError, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { Spinner } from "@/components/ui/spinner"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { useTranslation } from "@/i18n"
import type { AgentCatalogEntry } from "@/types/chat"
import { AgentConfiguration } from "@/pages/agent/components/AgentConfiguration"

export function AgentCard({
  agent,
  onUpdated,
}: {
  agent: AgentCatalogEntry
  onUpdated: (updated: AgentCatalogEntry) => void
}) {
  const { t } = useTranslation()
  const formId = useId()
  const nameInput = useRef<HTMLInputElement>(null)
  const [open, setOpen] = useState(false)
  const [name, setName] = useState(agent.name)
  const [description, setDescription] = useState(agent.description)
  const [enabled, setEnabled] = useState(agent.enabled)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")
  const Icon = agent.is_subagent ? Network : Bot
  const agentType = agent.is_subagent
    ? t("Sub agent")
    : agent.id === "LeaderAgent" ? t("Main agent") : t("Agent")
  const hasChanges = name.trim() !== agent.name || description !== agent.description || enabled !== agent.enabled
  const canSave = hasChanges && name.trim().length > 0 && name.trim().length <= 128 && !saving

  function handleOpenChange(nextOpen: boolean) {
    if (saving) return
    if (nextOpen) {
      setName(agent.name)
      setDescription(agent.description)
      setEnabled(agent.enabled)
      setError("")
    }
    setOpen(nextOpen)
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canSave) return
    setSaving(true)
    setError("")
    try {
      const updated = await updateAgent(agent.id, { name: name.trim(), description, enabled })
      onUpdated(updated)
      setOpen(false)
      toast.success(t("Agent updated"))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("Request failed"))
    } finally {
      setSaving(false)
    }
  }

  return (
    <article aria-label={agent.name} className="h-full">
      <Sheet open={open} onOpenChange={handleOpenChange}>
        <Card className="relative h-full cursor-pointer hover:border-input hover:bg-muted">
          <CardHeader>
            <div className="flex min-w-0 items-center gap-2.5">
              <span className="grid size-8 shrink-0 place-items-center rounded-[7px] border border-border bg-secondary text-secondary-foreground">
                <Icon className="size-4" aria-hidden />
              </span>
              <div className="min-w-0 space-y-1">
                <h3 className="truncate text-sm font-semibold">{agent.name}</h3>
                <p className="text-xs text-muted-foreground">{agentType}</p>
              </div>
            </div>
          </CardHeader>
          <CardContent className="flex flex-1 flex-col gap-2.5">
            <p className="line-clamp-2 min-h-[2.8em] break-words text-[13px] leading-[1.4] text-muted-foreground">
              {agent.description || t("No description")}
            </p>
            <div className="mt-auto flex items-center justify-between gap-3">
              <Badge variant={agent.enabled ? "success" : "default"}>
                {t(agent.enabled ? "Enabled" : "Disabled")}
              </Badge>
              <span aria-hidden className="inline-flex h-6 items-center gap-1 rounded-sm border border-input bg-card px-2 text-xs">
                {t("View details")} <ArrowRight className="size-3.5" />
              </span>
            </div>
          </CardContent>
          <SheetTrigger render={<Button variant="ghost" aria-label={t("View {{name}} details", { name: agent.name })}
            className="absolute inset-0 z-10 h-full w-full rounded-lg border-0 p-0 hover:bg-transparent focus-visible:ring-inset" />} />
        </Card>

        <SheetContent side="right" showCloseButton={false} initialFocus={nameInput}
          className="gap-0 rounded-none data-[side=right]:w-[30rem] data-[side=right]:max-w-[30rem]">
          <SheetHeader className="shrink-0 border-b border-border p-6 pr-12">
            <SheetTitle className="break-words text-lg">{agent.name}</SheetTitle>
            <SheetDescription className="sr-only">{t("Agent details")}</SheetDescription>
            <SheetClose render={<Button variant="ghost" size="icon-sm" className="absolute top-4 right-4" disabled={saving} aria-label={t("Close")} />}>
              <X aria-hidden />
            </SheetClose>
          </SheetHeader>
          <form id={formId} className="min-h-0 flex-1 space-y-6 overflow-y-auto p-6" onSubmit={handleSave} aria-busy={saving}>
            <dl className="grid grid-cols-[auto_minmax(0,1fr)] items-start gap-x-6 gap-y-3 border-b border-border pb-6 text-sm">
              <dt className="text-muted-foreground">{t("Agent ID")}</dt><dd className="break-words">{agent.id}</dd>
              <dt className="text-muted-foreground">{t("Agent type")}</dt><dd>{agentType}</dd>
            </dl>
            <Field>
              <FieldLabel htmlFor={`${formId}-name`}>{t("Agent name")}</FieldLabel>
              <Input id={`${formId}-name`} ref={nameInput} value={name} onChange={(event) => setName(event.target.value)}
                maxLength={128} required disabled={saving} />
            </Field>
            <Field>
              <FieldLabel htmlFor={`${formId}-description`}>{t("Description")}</FieldLabel>
              <Textarea id={`${formId}-description`} value={description} onChange={(event) => setDescription(event.target.value)}
                rows={7} className="h-40 min-h-0 resize-none overflow-y-auto field-sizing-fixed" disabled={saving} />
            </Field>
            <Field orientation="horizontal">
              <FieldLabel htmlFor={`${formId}-enabled`} className="flex-1">{t("Enable agent")}</FieldLabel>
              <Switch id={`${formId}-enabled`} checked={enabled} onCheckedChange={setEnabled} disabled={saving} />
            </Field>
            {open && <AgentConfiguration agentId={agent.id} />}
            {error && <FieldError>{error}</FieldError>}
          </form>
          <SheetFooter className="shrink-0 flex-row justify-end border-t border-border p-4">
            <SheetClose render={<Button variant="outline" disabled={saving} />}>{t("Cancel")}</SheetClose>
            <Button type="submit" form={formId} disabled={!canSave}>
              {saving ? <Spinner aria-hidden /> : <Save aria-hidden />}
              {t(saving ? "Saving..." : "Save changes")}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </article>
  )
}
