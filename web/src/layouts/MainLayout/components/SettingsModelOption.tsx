import { useId } from "react";
import { Cpu } from "lucide-react";
import { cn } from "cn";

import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Item, ItemContent, ItemTitle } from "@/components/ui/item";
import { Label } from "@/components/ui/label";
import { useTranslation } from "@/i18n";
import type { SettingsModel } from "@/types/model";
import { ModelCapabilities } from "./ModelCapabilities";

interface SettingsModelOptionProps {
  model: SettingsModel;
  isSelected?: boolean;
  isDisabled?: boolean;
  onSelectedChange?: (isSelected: boolean) => void;
}

const categoryLabels: Record<"embedding" | "rerank", string> = {
  embedding: "Embedding",
  rerank: "Rerank",
};

export function SettingsModelOption({
  model,
  isSelected = false,
  isDisabled = false,
  onSelectedChange,
}: SettingsModelOptionProps) {
  const { t } = useTranslation();
  const inputId = useId();
  const titleId = useId();
  const categoryLabel = model.category && model.category !== "chat" ? categoryLabels[model.category] : null;

  return (
    <Item
      render={onSelectedChange ? <Label htmlFor={inputId} /> : undefined}
      role="listitem"
      aria-labelledby={titleId}
      aria-disabled={isDisabled || undefined}
      data-selected={onSelectedChange ? isSelected : undefined}
      variant={isSelected ? "muted" : "outline"}
      size="sm"
      className={cn(
        "min-w-0 flex-nowrap items-start gap-2.5 p-2.5",
        onSelectedChange && "cursor-pointer hover:bg-accent",
        isSelected && "hover:bg-selection",
        isDisabled && "cursor-not-allowed opacity-50",
      )}
    >
      {onSelectedChange ? (
        <Checkbox
          id={inputId}
          aria-labelledby={titleId}
          checked={isSelected}
          disabled={isDisabled}
          onCheckedChange={(checked) => onSelectedChange(checked === true)}
          className="mt-0.5 size-3.5"
        />
      ) : (
        <Cpu aria-hidden="true" className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
      )}
      <ItemContent className="min-w-0 gap-1.5">
        <div className="flex items-center gap-2">
          <ItemTitle id={titleId} title={model.model_id} className="line-clamp-none block min-w-0 flex-1 text-[13px] leading-tight font-medium break-all">
            {model.model_id}
          </ItemTitle>
          {categoryLabel && (
            <Badge variant="outline" className="shrink-0 text-[10px]">
              {t(categoryLabel)}
            </Badge>
          )}
        </div>
        <ModelCapabilities capabilities={model.capabilities} />
      </ItemContent>
    </Item>
  );
}
