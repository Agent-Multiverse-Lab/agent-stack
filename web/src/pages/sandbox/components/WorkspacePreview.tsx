import { useEffect, useRef, useState, type RefObject } from "react";
import { FilePenLine, FileText, Maximize2, Minimize2, X } from "lucide-react";

import { readSandboxFile, updateSandboxFile } from "@/api/sandbox";
import { FileContentViewer, isMarkdownPath } from "@/components/common/file-content-viewer";
import { Button } from "@/components/ui/button";
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useTranslation } from "@/i18n";
import type { WorkspaceEntry } from "@/pages/sandbox/types";

interface WorkspacePreviewProps {
  threadId: string;
  entry: WorkspaceEntry | null;
  container: RefObject<HTMLDivElement | null>;
  expanded: boolean;
  onExpand: () => void;
  onClose: () => void;
  returnFocus: RefObject<HTMLElement | null>;
  editing: boolean;
  onEditingChange: (editing: boolean) => void;
  onSaved: () => void;
}

export default function WorkspacePreview({
  threadId, entry, container, expanded, onExpand, onClose, returnFocus,
  editing, onEditingChange, onSaved,
}: WorkspacePreviewProps) {
  const { t } = useTranslation();
  const [viewMode, setViewMode] = useState<"preview" | "source">("preview");
  const [file, setFile] = useState({ path: "", content: "", error: "", loading: false, truncated: false });
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const generation = useRef(0);
  const path = entry?.path ?? "";

  useEffect(() => {
    if (!path) return;
    const loadGeneration = ++generation.current;
    setViewMode("preview");
    setSaveError("");
    setDraft("");
    setFile({ path, content: "", error: "", loading: true, truncated: false });
    const request = editing ? readSandboxFile(threadId, path, true) : readSandboxFile(threadId, path);
    void request
      .then((response) => {
        if (generation.current === loadGeneration) {
          setFile({ path, content: response.content, error: "", loading: false, truncated: response.truncated });
          setDraft(response.content.replace(/\r\n/g, "\n"));
        }
      })
      .catch((caught: unknown) => {
        if (generation.current === loadGeneration) setFile({ path, content: "", error: caught instanceof Error ? caught.message : t("Request failed"), loading: false, truncated: false });
      });
    return () => { generation.current += 1; };
  }, [path, threadId, editing, t]);

  const current = file.path === path;
  const canEdit = current && !file.loading && !file.error && !file.truncated;
  async function save() {
    if (!canEdit || saving) return;
    setSaving(true);
    setSaveError("");
    const savedGeneration = generation.current;
    try {
      await updateSandboxFile(threadId, path, draft, file.content);
      onSaved();
      if (generation.current === savedGeneration) onEditingChange(false);
    } catch (caught) {
      if (generation.current === savedGeneration) setSaveError(caught instanceof Error ? caught.message : t("Request failed"));
    } finally {
      setSaving(false);
    }
  }
  return (
    <Sheet open={entry !== null} modal={false} disablePointerDismissal
      onOpenChange={(open) => { if (!open && !saving) onClose(); }}>
      <SheetContent
        container={container}
        side="right"
        showOverlay={false}
        showCloseButton={false}
        initialFocus={false}
        finalFocus={() => returnFocus.current?.isConnected ? returnFocus.current : false}
        className="absolute! inset-0! z-10 h-full! w-full! max-w-none! gap-0 rounded-none border-0 bg-card p-0 shadow-none motion-reduce:transition-none"
      >
        <SheetHeader className="flex h-12 shrink-0 flex-row items-center gap-2 px-5 py-2">
          <FileText className="size-5 shrink-0 text-muted-foreground" strokeWidth={1.5} />
          <SheetTitle className="min-w-0 flex-1 truncate text-sm font-medium">
            {entry?.name ?? t("File preview")}
          </SheetTitle>
          <SheetDescription className="sr-only">{t("File preview")}</SheetDescription>
          {!editing && canEdit && <Button type="button" variant="ghost" size="icon-sm" className="rounded-md"
            aria-label={t("Edit content")} onClick={() => onEditingChange(true)}><FilePenLine /></Button>}
          <Button type="button" variant="ghost" size="icon-sm" className="rounded-md"
            aria-label={t(expanded ? "Restore preview width" : "Expand preview")} onClick={onExpand}>
            {expanded ? <Minimize2 /> : <Maximize2 />}
          </Button>
          <SheetClose disabled={saving} render={<Button type="button" variant="ghost" size="icon-sm" className="rounded-md" aria-label={t("Close preview")} />}>
            <X />
          </SheetClose>
        </SheetHeader>
        {!editing && isMarkdownPath(path) && (
          <Tabs value={viewMode} onValueChange={(value) => setViewMode(value as "preview" | "source")}
            className="shrink-0 px-5 pb-2">
            <TabsList className="gap-1">
              <TabsTrigger value="preview" className="rounded-sm border-b-2 border-transparent px-3 py-1.5 text-xs hover:bg-accent data-active:border-primary data-active:bg-selection data-active:text-selection-foreground data-active:hover:bg-selection">
                {t("Preview file")}
              </TabsTrigger>
              <TabsTrigger value="source" className="rounded-sm border-b-2 border-transparent px-3 py-1.5 text-xs hover:bg-accent data-active:border-primary data-active:bg-selection data-active:text-selection-foreground data-active:hover:bg-selection">
                {t("Source code")}
              </TabsTrigger>
            </TabsList>
          </Tabs>
        )}
        {editing ? (
          <form className="flex min-h-0 flex-1 flex-col" onSubmit={(event) => { event.preventDefault(); void save(); }}>
            {canEdit ? <Textarea autoFocus aria-label={t("File content")} value={draft} maxLength={200_000} disabled={saving}
              onChange={(event) => setDraft(event.target.value)}
              className="h-full min-h-0 flex-1 resize-none rounded-none border-0 px-5 py-4 font-mono text-xs leading-6 field-sizing-fixed" />
              : <div className="min-h-0 flex-1 overflow-auto">
                  {file.truncated && current ? <p role="alert" className="px-5 py-4 text-sm text-destructive">{t("This file is too large to edit")}</p>
                    : <FileContentViewer path={path} content="" loading={!current || file.loading} error={current ? file.error : ""} />}
                </div>}
            {saveError && <p role="alert" className="px-5 py-2 text-sm text-destructive">{saveError}</p>}
            <div className="flex shrink-0 justify-end gap-2 px-5 py-3">
              <Button type="button" variant="ghost" disabled={saving} onClick={() => onEditingChange(false)}>{t("Cancel")}</Button>
              <Button type="submit" disabled={!canEdit || saving || draft === file.content.replace(/\r\n/g, "\n")}>
                {t(saving ? "Processing..." : "Save")}
              </Button>
            </div>
          </form>
        ) : <div className="flex min-h-0 flex-1 flex-col overflow-auto">
          <FileContentViewer path={path} content={current ? file.content : ""}
            loading={!current || file.loading} error={current ? file.error : ""}
            truncated={current && file.truncated} viewMode={viewMode} />
        </div>}
      </SheetContent>
    </Sheet>
  );
}
