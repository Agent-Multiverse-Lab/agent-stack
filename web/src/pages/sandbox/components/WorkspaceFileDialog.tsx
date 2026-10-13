import { useState } from "react";

import { deleteSandboxFile, renameSandboxFile } from "@/api/sandbox";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useTranslation } from "@/i18n";
import type { WorkspaceEntry } from "@/pages/sandbox/types";

interface WorkspaceFileDialogProps {
  threadId: string;
  entry: WorkspaceEntry;
  action: "rename" | "delete";
  onClose: () => void;
  onComplete: (path: string | null) => void;
}

export default function WorkspaceFileDialog({ threadId, entry, action, onClose, onComplete }: WorkspaceFileDialogProps) {
  const { t } = useTranslation();
  const [name, setName] = useState(entry.name);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const validName = name.trim() && ![".", ".."].includes(name.trim()) && !/[/\\\0]/.test(name);

  async function submit() {
    setSaving(true);
    setError("");
    try {
      if (action === "rename") {
        const response = await renameSandboxFile(threadId, entry.path, name.trim());
        onComplete(response.path);
      } else {
        await deleteSandboxFile(threadId, entry.path);
        onComplete(null);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("Request failed"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open && !saving) onClose(); }}>
      <DialogContent showCloseButton={!saving}>
        <DialogHeader>
          <DialogTitle>{t(action === "rename" ? "Rename file" : "Delete file")}</DialogTitle>
          <DialogDescription className={action === "rename" ? "sr-only" : "break-words"}>
            {action === "rename" ? entry.name : t("Delete {{name}}?", { name: entry.name })}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={(event) => { event.preventDefault(); void submit(); }}>
          {action === "rename" && <Input autoFocus aria-label={t("File name")} value={name} maxLength={255}
            disabled={saving} onChange={(event) => setName(event.target.value)} />}
          {error && <p role="alert" className="mt-3 text-sm text-destructive">{error}</p>}
          <DialogFooter className="mt-4">
            <Button type="button" variant="ghost" disabled={saving} onClick={onClose}>{t("Cancel")}</Button>
            <Button type="submit" variant={action === "delete" ? "destructive" : "default"}
              disabled={saving || (action === "rename" && (!validName || name.trim() === entry.name))}>
              {t(saving ? "Processing..." : action === "rename" ? "Save" : "Delete")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
