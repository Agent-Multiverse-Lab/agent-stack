import { useId } from "react";
import { Cpu } from "lucide-react";
import { cn } from "cn";

import { Checkbox } from "@/components/ui/checkbox";
import { Item, ItemContent, ItemTitle } from "@/components/ui/item";
import { Label } from "@/components/ui/label";
import type { SettingsModel } from "@/types/model";
import { ModelCapabilities } from "./ModelCapabilities";

interface SettingsModelOptionProps {
  model: SettingsModel;
  isSelected?: boolean;
  isDisabled?: boolean;
  onSelectedChange?: (isSelected: boolean) => void;
}

export function SettingsModelOption({
  model,
  isSelected = false,
  isDisabled = false,
  onSelectedChange,
}: SettingsModelOptionProps) {
  const inputId = useId();
  const titleId = useId();

  return (
    <Item
      render={onSelectedChange ? <Label htmlFor={inputId} /> : undefined}
      role="listitem"
      aria-labelledby={titleId}
      aria-disabled={isDisabled || undefined}
      data-selected={onSelectedChange ? isSelected : undefined}
      variant={isSelected ? "muted" : "outline"}
      className={cn(
        "min-w-0 flex-nowrap items-start gap-3 p-3",
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
          className="mt-0.5"
        />
      ) : (
        <Cpu aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
      )}
      <ItemContent className="min-w-0 gap-2">
        <ItemTitle id={titleId} title={model.model_id} className="line-clamp-none block w-full break-all">
          {model.model_id}
        </ItemTitle>
        <ModelCapabilities capabilities={model.capabilities} />
      </ItemContent>
    </Item>
  );
}
