import { Label } from "@/components/ui/label";
import { useState } from "react";
import { FolderPlus, StickyNote, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { CreateNotePayload } from "@/types/library";
import { useTranslation } from "@/i18n";

export default function CreateDialog({
  kind,
  close,
  create,
}: {
  kind: "folder" | "note";
  close: () => void;
  create: (value: string | CreateNotePayload) => void;
}) {
  const { t } = useTranslation();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  return (
    <Dialog open onOpenChange={(open) => { if (!open) close(); }}>
      <DialogContent
        showCloseButton={false}
        overlayClassName="bg-graphite/40"
        className="w-full max-w-md gap-0 overflow-hidden rounded-xl border border-graphite/12 bg-paper p-5 text-graphite shadow-lg sm:max-w-md"
      >
        <DialogHeader className="flex flex-row items-center justify-between border-b border-graphite/8 pb-3">
          <DialogTitle className="flex items-center gap-2 text-sm font-semibold">
            {kind === "folder" ? (
              <FolderPlus size={18} />
            ) : (
              <StickyNote size={18} />
            )}
            {kind === "folder" ? t("Create New Folder") : t("Create Quick Note")}
          </DialogTitle>
          <DialogClose render={<Button variant="ghost" size="icon-sm" />} aria-label={t("Close")}>
            <X size={14} />
          </DialogClose>
        </DialogHeader>
        <DialogDescription className="sr-only">
          {kind === "folder" ? t("Create a folder in your library.") : t("Create a quick note in your library.")}
        </DialogDescription>
        <form
          className="mt-4 grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (!title.trim()) return;
            create(
              kind === "folder"
                ? title.trim()
                : { title: title.trim(), content: content.trim() },
            );
            close();
          }}
        >
          <Label className="grid gap-1 text-xs font-medium text-slate">
            {kind === "folder" ? t("Folder Name") : t("Title")}
            <Input
              autoFocus
              required
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder={
                kind === "folder" ? t("e.g. Project Assets") : t("Note title...")
              }
              className="h-9 rounded-md border-graphite/14 bg-mist/40 px-3 text-xs text-graphite"
            />
          </Label>
          {kind === "note" && (
            <Label className="grid gap-1 text-xs font-medium text-slate">
              {t("Content")}
              <Textarea
                value={content}
                onChange={(event) => setContent(event.target.value)}
                rows={4}
                placeholder={t("Write your note content here...")}
                className="rounded-md border-graphite/14 bg-mist/40 p-3 text-xs text-graphite"
              />
            </Label>
          )}
          <DialogFooter className="-mx-0 -mb-0 flex-row justify-end border-0 bg-transparent p-0 pt-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-xs text-slate"
              onClick={close}
            >
              {t("Cancel")}
            </Button>
            <Button
              type="submit"
              size="sm"
              className="bg-graphite px-4 text-xs text-paper hover:bg-graphite/90"
            >
              {kind === "folder" ? t("Create") : t("Save Note")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
