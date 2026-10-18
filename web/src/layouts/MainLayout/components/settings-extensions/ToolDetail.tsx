import { useRef, type RefObject } from "react";
import { ArrowLeftIcon, BracesIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useTranslation } from "@/i18n";
import type { McpToolPreview } from "./extension-preview-data";
import { ToolSchemaSection } from "./ToolSchemaSection";

type ToolDetailProps = {
  tool: McpToolPreview;
  isOpen: boolean;
  returnFocusRef: RefObject<HTMLElement | null>;
  fallbackFocusRef: RefObject<HTMLElement | null>;
  onClose: () => void;
  onClosed: () => void;
};

export function ToolDetail({ tool, isOpen, returnFocusRef, fallbackFocusRef, onClose, onClosed }: ToolDetailProps) {
  const { t } = useTranslation();
  const backRef = useRef<HTMLButtonElement>(null);
  return <Dialog
    open={isOpen}
    onOpenChange={(open) => { if (!open) onClose(); }}
    onOpenChangeComplete={(open) => { if (!open) onClosed(); }}
  >
    <DialogContent
      className="z-[121] flex max-h-[min(740px,calc(100dvh-48px))] w-[calc(100vw-48px)] max-w-[640px] flex-col gap-0 overflow-hidden p-0"
      overlayClassName="z-[120]"
      forceRenderOverlay
      initialFocus={backRef}
      finalFocus={() => returnFocusRef.current?.isConnected ? returnFocusRef.current : fallbackFocusRef.current}
    >
      <div className="flex min-h-14 shrink-0 items-center gap-3 border-b px-5 pr-16">
        <Button type="button" ref={backRef} variant="ghost" size="sm" onClick={onClose}>
          <ArrowLeftIcon aria-hidden="true" />{t("Back to tools")}
        </Button>
        <Badge className="ml-auto">{t("Example metadata")}</Badge>
      </div>
      <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-6 py-5">
        <DialogHeader>
          <div className="mb-1 flex size-10 items-center justify-center rounded-lg bg-muted text-muted-foreground">
            <BracesIcon aria-hidden="true" className="size-5" />
          </div>
          <DialogTitle className="break-all font-mono text-lg">{tool.name}</DialogTitle>
          <DialogDescription>{t(tool.description || "Description unavailable")}</DialogDescription>
        </DialogHeader>
        <ToolSchemaSection title={t("Input schema")} schema={tool.inputSchema} emptyMessage={t("Input schema unavailable")} />
        <ToolSchemaSection title={t("Output schema")} schema={tool.outputSchema} emptyMessage={t("Output schema unavailable")} />
      </div>
    </DialogContent>
  </Dialog>;
}
