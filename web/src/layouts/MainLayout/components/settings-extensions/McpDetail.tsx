import { type RefObject, useId } from "react";
import { LockKeyholeIcon, PlugIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useTranslation } from "@/i18n";
import type { McpPreview } from "./extension-preview-data";

type McpDetailProps = {
  draft: McpPreview;
  onChange: (draft: McpPreview) => void;
  nameInputRef: RefObject<HTMLInputElement | null>;
  activeTab: string;
  onTabChange: (tab: string) => void;
};

export function McpDetail({ draft, onChange, nameInputRef, activeTab, onTabChange }: McpDetailProps) {
  const { t } = useTranslation();
  const fieldId = useId();
  return (
    <Tabs value={activeTab} onValueChange={(value) => onTabChange(String(value))} className="gap-5">
      <TabsList aria-label={t("MCP configuration sections")} className="w-full justify-start gap-6 border-b">
        <TabsTrigger value="general" className="pb-3 data-active:border-b-2 data-active:border-primary">{t("Basic configuration")}</TabsTrigger>
        <TabsTrigger value="connection" className="pb-3 data-active:border-b-2 data-active:border-primary">{t("Connection settings")}</TabsTrigger>
      </TabsList>
      <TabsContent value="general">
        <FieldGroup className="gap-5">
          <Field orientation="horizontal" className="items-center justify-between">
            <FieldLabel htmlFor={`${fieldId}-enabled`}>{t("Enabled")}</FieldLabel>
            <Switch id={`${fieldId}-enabled`} checked={draft.isEnabled} onCheckedChange={(isEnabled) => onChange({ ...draft, isEnabled })} />
          </Field>
          <Field>
            <FieldLabel htmlFor={`${fieldId}-name`}>{t("Service name")}</FieldLabel>
            <Input ref={nameInputRef} id={`${fieldId}-name`} name="name" required autoComplete="off"
              value={draft.name} onChange={(event) => onChange({ ...draft, name: event.target.value })} />
          </Field>
          <Field>
            <FieldLabel htmlFor={`${fieldId}-description`}>{t("Description")}</FieldLabel>
            <Textarea id={`${fieldId}-description`} name="description" className="min-h-24 resize-y" rows={3}
              value={draft.description} onChange={(event) => onChange({ ...draft, description: event.target.value })} />
          </Field>
          <section className="space-y-3" aria-label={t("Example tools")}>
            <h3 className="text-xs font-medium text-muted-foreground">{t("Example tools")}</h3>
            {draft.tools.length ? <div className="flex flex-wrap gap-2">
              {draft.tools.map((tool) => <Badge className="font-mono" key={tool}>{tool}</Badge>)}
            </div> : <p className="text-sm text-muted-foreground">{t("No example tools")}</p>}
          </section>
        </FieldGroup>
      </TabsContent>
      <TabsContent value="connection">
        <FieldGroup className="gap-5">
          <Field>
            <FieldLabel htmlFor={`${fieldId}-transport`}>{t("Transport")}</FieldLabel>
            <Select value={draft.transport} onValueChange={(transport) => { if (transport === "http" || transport === "sse") onChange({ ...draft, transport }); }}>
              <SelectTrigger id={`${fieldId}-transport`} className="w-full"><SelectValue>{draft.transport === "http" ? "Streamable HTTP" : "SSE"}</SelectValue></SelectTrigger>
              <SelectContent><SelectItem value="http">Streamable HTTP</SelectItem><SelectItem value="sse">SSE</SelectItem></SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel htmlFor={`${fieldId}-endpoint`}>{t("Server address")}</FieldLabel>
            <Input id={`${fieldId}-endpoint`} name="endpoint" type="url" required autoComplete="off" spellCheck={false} className="font-mono text-xs"
              value={draft.endpoint} placeholder="https://mcp.example.invalid/service"
              onChange={(event) => onChange({ ...draft, endpoint: event.target.value })} />
          </Field>
          <Field>
            <FieldLabel htmlFor={`${fieldId}-authentication`}>{t("Authentication")}</FieldLabel>
            <Select value={draft.authentication} onValueChange={(authentication) => { if (authentication === "none" || authentication === "bearer") onChange({ ...draft, authentication }); }}>
              <SelectTrigger id={`${fieldId}-authentication`} className="w-full"><SelectValue>{t(draft.authentication === "bearer" ? "Bearer token" : "None")}</SelectValue></SelectTrigger>
              <SelectContent><SelectItem value="none">{t("None")}</SelectItem><SelectItem value="bearer">{t("Bearer token")}</SelectItem></SelectContent>
            </Select>
          </Field>
          <p className="flex items-start gap-2 text-xs leading-5 text-muted-foreground">
            <LockKeyholeIcon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            {t("Credentials are unavailable in local preview. Do not enter secrets.")}
          </p>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground">{t("Connection not tested")}</p>
            <Button type="button" variant="outline" disabled><PlugIcon aria-hidden="true" />{t("Connection testing unavailable")}</Button>
          </div>
        </FieldGroup>
      </TabsContent>
    </Tabs>
  );
}
