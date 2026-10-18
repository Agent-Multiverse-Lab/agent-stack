import { BlocksIcon, ChevronRightIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/i18n";
import type { SkillPreview } from "./extension-preview-data";

type SkillCardProps = {
  item: SkillPreview;
  onOpen: (target: HTMLButtonElement) => void;
};

export function SkillCard({ item, onOpen }: SkillCardProps) {
  const { t } = useTranslation();

  return (
    <Button
      type="button"
      variant="ghost"
      className="grid h-auto min-h-20 w-full grid-cols-[minmax(0,1fr)_144px_120px_16px] gap-4 rounded-none px-3 py-4 text-left"
      aria-label={item.name}
      aria-haspopup="dialog"
      onClick={(event) => onOpen(event.currentTarget)}
    >
      <span className="flex min-w-0 items-center gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
          <BlocksIcon className="size-4" aria-hidden="true" />
        </span>
        <span className="flex min-w-0 flex-col gap-1">
          <span className="truncate font-medium">{item.name}</span>
          <span className="truncate text-xs text-muted-foreground">{item.id}</span>
        </span>
      </span>
      <span className="text-xs text-muted-foreground">
        {t(item.scope === "all" ? "All agents" : "Research agents")}
      </span>
      <Badge variant={item.isEnabled ? "secondary" : "default"}>
        {t(item.isEnabled ? "Enabled" : "Disabled")}
      </Badge>
      <ChevronRightIcon className="size-4 text-muted-foreground" aria-hidden="true" />
    </Button>
  );
}
