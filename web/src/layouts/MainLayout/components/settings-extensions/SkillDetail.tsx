import { type RefObject, useId } from "react";
import { FileTextIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useTranslation } from "@/i18n";
import type { SkillPreview } from "./extension-preview-data";

type SkillDetailProps = {
  draft: SkillPreview;
  onChange: (draft: SkillPreview) => void;
  nameInputRef: RefObject<HTMLInputElement | null>;
  activeTab: string;
  onTabChange: (tab: string) => void;
};

export function SkillDetail({ draft, onChange, nameInputRef, activeTab, onTabChange }: SkillDetailProps) {
  const { t } = useTranslation();
  const fieldId = useId();
  return (
    <Tabs value={activeTab} onValueChange={(value) => onTabChange(String(value))} className="gap-5">
      <TabsList aria-label={t("Skill configuration sections")} className="w-full justify-start gap-6 border-b">
        <TabsTrigger value="general" className="pb-3 data-active:border-b-2 data-active:border-primary">{t("Basic configuration")}</TabsTrigger>
        <TabsTrigger value="files" className="pb-3 data-active:border-b-2 data-active:border-primary">{t("Example file")}</TabsTrigger>
      </TabsList>
      <TabsContent value="general">
        <FieldGroup className="gap-5">
          <Field orientation="horizontal" className="items-center justify-between">
            <FieldLabel htmlFor={`${fieldId}-enabled`}>{t("Enabled")}</FieldLabel>
            <Switch id={`${fieldId}-enabled`} checked={draft.isEnabled} onCheckedChange={(isEnabled) => onChange({ ...draft, isEnabled })} />
          </Field>
          <Field>
            <FieldLabel htmlFor={`${fieldId}-name`}>{t("Skill name")}</FieldLabel>
            <Input ref={nameInputRef} id={`${fieldId}-name`} name="name" required autoComplete="off"
              value={draft.name} onChange={(event) => onChange({ ...draft, name: event.target.value })} />
          </Field>
          <Field>
            <FieldLabel htmlFor={`${fieldId}-description`}>{t("Description")}</FieldLabel>
            <Textarea id={`${fieldId}-description`} name="description" className="min-h-24 resize-y" rows={3}
              value={draft.description} onChange={(event) => onChange({ ...draft, description: event.target.value })} />
          </Field>
          <Field>
            <FieldLabel htmlFor={`${fieldId}-scope`}>{t("Scope")}</FieldLabel>
            <Select value={draft.scope} onValueChange={(scope) => { if (scope === "all" || scope === "research") onChange({ ...draft, scope }); }}>
              <SelectTrigger id={`${fieldId}-scope`} className="w-full"><SelectValue>{t(draft.scope === "all" ? "All agents" : "Research agents")}</SelectValue></SelectTrigger>
              <SelectContent><SelectItem value="all">{t("All agents")}</SelectItem><SelectItem value="research">{t("Research agents")}</SelectItem></SelectContent>
            </Select>
          </Field>
          <section className="space-y-3" aria-label={t("Example capabilities")}>
            <h3 className="text-xs font-medium text-muted-foreground">{t("Example capabilities")}</h3>
            {draft.capabilities.length ? <div className="flex flex-wrap gap-2">
              {draft.capabilities.map((capability) => <Badge key={capability}>{t(capability)}</Badge>)}
            </div> : <p className="text-sm text-muted-foreground">{t("No example capabilities")}</p>}
          </section>
        </FieldGroup>
      </TabsContent>
      <TabsContent value="files" className="space-y-4">
        <p className="flex items-center gap-2 text-sm font-medium"><FileTextIcon aria-hidden="true" className="size-4" />SKILL.md <Badge>{t("Read only")}</Badge></p>
        <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-lg bg-muted p-4 font-mono text-xs leading-6 text-muted-foreground">{t(draft.fileContent)}</pre>
      </TabsContent>
    </Tabs>
  );
}
