import { useId } from "react";
import { Badge } from "@/components/ui/badge";
import { useTranslation } from "@/i18n";
import type { ToolSchema } from "./extension-preview-data";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

type ToolSchemaSectionProps = {
  title: string;
  schema?: ToolSchema;
  emptyMessage: string;
};

export function ToolSchemaSection({ title, schema, emptyMessage }: ToolSchemaSectionProps) {
  const { t } = useTranslation();
  const titleId = useId();
  const properties = isRecord(schema) && isRecord(schema.properties) ? schema.properties : null;
  const required = isRecord(schema) && Array.isArray(schema.required) ? schema.required : [];
  return <section aria-labelledby={titleId} className="space-y-3">
    <h3 id={titleId} className="text-sm font-medium">{title}</h3>
    {schema === undefined ? <p className="text-sm text-muted-foreground">{emptyMessage}</p> : <>
      {properties && Object.keys(properties).length > 0 && <dl className="divide-y text-xs">
        {Object.entries(properties).map(([name, value]) => {
          const property = isRecord(value) ? value : {};
          const type = typeof property.type === "string" ? property.type
            : Array.isArray(property.type) && property.type.every((part) => typeof part === "string") ? property.type.join(" | ") : null;
          return <div key={name} className="space-y-1 py-2 first:pt-0">
            <dt className="flex flex-wrap items-center gap-2">
              <span className="break-all font-mono font-medium">{name}</span>
              <span className="font-mono text-muted-foreground">{type || t("Type unspecified")}</span>
              {required.includes(name) && <Badge>{t("Required")}</Badge>}
            </dt>
            {typeof property.description === "string" && <dd className="leading-5 text-muted-foreground">{t(property.description)}</dd>}
          </div>;
        })}
      </dl>}
      {properties && Object.keys(properties).length === 0 && <p className="text-xs text-muted-foreground">{t("No declared parameters")}</p>}
      <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-muted p-4 font-mono text-xs leading-5 text-muted-foreground">{JSON.stringify(schema, null, 2)}</pre>
    </>}
  </section>;
}
