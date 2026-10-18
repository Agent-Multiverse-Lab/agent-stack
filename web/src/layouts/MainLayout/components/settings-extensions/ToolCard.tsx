import { BracesIcon, ChevronRightIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/i18n";
import type { McpToolPreview } from "./extension-preview-data";

type ToolCardProps = {
  tool: McpToolPreview;
  onOpen: (target: HTMLButtonElement) => void;
};

export function ToolCard({ tool, onOpen }: ToolCardProps) {
  const { t } = useTranslation();
  return <Button
    type="button"
    variant="ghost"
    className="h-auto min-h-20 w-full justify-start gap-3 rounded-none px-2 py-4 text-left"
    aria-label={tool.name}
    aria-haspopup="dialog"
    onClick={(event) => onOpen(event.currentTarget)}
  >
    <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
      <BracesIcon className="size-4" aria-hidden="true" />
    </span>
    <span className="flex min-w-0 flex-1 flex-col gap-1">
      <span className="break-all font-mono text-xs font-medium">{tool.name}</span>
      <span className="whitespace-normal text-xs leading-5 text-muted-foreground">{t(tool.description || "Description unavailable")}</span>
    </span>
    <ChevronRightIcon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
  </Button>;
}
