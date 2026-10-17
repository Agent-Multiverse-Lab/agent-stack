import { useRef, useState, type RefObject } from "react";
import { ArrowLeft, Info } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useTranslation } from "@/i18n";
import { SkillDetail } from "./SkillDetail";
import { McpDetail } from "./McpDetail";
import { isPreviewDirty, type ExtensionPreview } from "./extension-preview-data";

interface ExtensionDialogProps {
  item: ExtensionPreview;
  isNew: boolean;
  isOpen: boolean;
  returnFocusRef: RefObject<HTMLElement | null>;
  fallbackFocusRef: RefObject<HTMLElement | null>;
  onApply: (item: ExtensionPreview) => void;
  onClose: () => void;
  onClosed: () => void;
}

export function ExtensionDialog({
  item, isNew, isOpen, returnFocusRef, fallbackFocusRef, onApply, onClose, onClosed,
}: ExtensionDialogProps) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState("general");
  const [draft, setDraft] = useState(item);
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [error, setError] = useState("");
  const backRef = useRef<HTMLButtonElement>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);
  const keepEditingRef = useRef<HTMLButtonElement>(null);
  const confirmReturnFocus = useRef<HTMLElement | null>(null);
  const shouldCloseAfterDiscard = useRef(false);
  const isDirty = isPreviewDirty(draft, item);

  function requestClose() {
    if (isDirty) {
      confirmReturnFocus.current = document.activeElement instanceof HTMLElement
        ? document.activeElement : nameInputRef.current;
      setIsConfirmOpen(true);
    } else onClose();
  }

  function applyPreview() {
    const name = draft.name.trim();
    if (!name) {
      setError(t("Enter a name for this example."));
      setActiveTab("general");
      requestAnimationFrame(() => nameInputRef.current?.focus());
      return;
    }
    if (draft.kind === "mcp" && !draft.endpoint.trim()) {
      setActiveTab("connection");
      setError(t("Enter an example server address."));
      return;
    }
    if (draft.kind === "mcp") {
      try {
        const address = new URL(draft.endpoint);
        if (!["http:", "https:"].includes(address.protocol) || address.username || address.password) throw new Error("Invalid example address");
      } catch {
        setActiveTab("connection");
        setError(t("Use an HTTP(S) example address without credentials."));
        return;
      }
    }
    onApply({ ...draft, name });
    onClose();
  }

  const title = isNew
    ? t(draft.kind === "skills" ? "Add example skill" : "Add example MCP service")
    : item.name;

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open, event) => {
        if (open) return;
        event.cancel();
        requestClose();
      }}
      onOpenChangeComplete={(open) => { if (!open) onClosed(); }}
    >
      <DialogContent
        className="z-[111] flex max-h-[min(740px,calc(100dvh-48px))] w-[calc(100vw-48px)] max-w-[584px] flex-col gap-0 overflow-hidden p-0"
        overlayClassName="z-[110]"
        forceRenderOverlay
        initialFocus={() => nameInputRef.current}
        finalFocus={() => returnFocusRef.current?.isConnected ? returnFocusRef.current : fallbackFocusRef.current}
      >
        <div className="flex min-h-14 shrink-0 items-center gap-3 border-b px-5 pr-16">
          <Button ref={backRef} variant="ghost" size="sm" onClick={requestClose}>
            <ArrowLeft aria-hidden="true" />
            {t("Back to list")}
          </Button>
          <Badge className="ml-auto">{t("Example configuration")}</Badge>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          <p className="mb-4 flex items-center gap-2 text-xs text-muted-foreground">
            <Info aria-hidden="true" className="size-3.5 shrink-0" />
            {t("Local preview · No server changes")}
          </p>
          <DialogHeader className="mb-5">
            <DialogTitle className="min-w-0 break-words">{title}</DialogTitle>
            <DialogDescription>
              {t("Changes only last in this preview. Nothing is saved to the server.")}
            </DialogDescription>
          </DialogHeader>

          <form noValidate id="extension-preview-form" onSubmit={(event) => { event.preventDefault(); applyPreview(); }}>
            {draft.kind === "skills"
              ? <SkillDetail draft={draft} onChange={setDraft} nameInputRef={nameInputRef} activeTab={activeTab} onTabChange={setActiveTab} />
              : <McpDetail draft={draft} onChange={setDraft} nameInputRef={nameInputRef} activeTab={activeTab} onTabChange={setActiveTab} />}
            {error && <p role="alert" className="mt-4 text-sm text-destructive">{error}</p>}
          </form>
        </div>

        <DialogFooter className="shrink-0 items-center justify-end gap-4 border-t px-6 py-4">
          <Button variant="outline" onClick={requestClose}>{t("Cancel")}</Button>
          <Button type="submit" form="extension-preview-form">{t("Apply to preview")}</Button>
        </DialogFooter>

        <Dialog
          open={isConfirmOpen}
          onOpenChange={(open) => { if (!open) setIsConfirmOpen(false); }}
          onOpenChangeComplete={(open) => {
            if (open || !shouldCloseAfterDiscard.current) return;
            shouldCloseAfterDiscard.current = false;
            onClose();
          }}
        >
          <DialogContent
            className="z-[121] max-w-sm"
            overlayClassName="z-[120]"
            forceRenderOverlay
            initialFocus={keepEditingRef}
            finalFocus={() => shouldCloseAfterDiscard.current ? false : confirmReturnFocus.current}
          >
            <DialogHeader>
              <DialogTitle>{t("Discard preview changes?")}</DialogTitle>
              <DialogDescription>{t("Your edits have not been applied to this local preview.")}</DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button ref={keepEditingRef} variant="outline" onClick={() => setIsConfirmOpen(false)}>{t("Keep editing")}</Button>
              <Button variant="destructive" onClick={() => {
                shouldCloseAfterDiscard.current = true;
                setIsConfirmOpen(false);
              }}>{t("Discard changes")}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </DialogContent>
    </Dialog>
  );
}
