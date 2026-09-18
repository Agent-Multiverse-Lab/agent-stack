import { useState } from "react";
import { FolderPlus, StickyNote, X } from "lucide-react";
import type { CreateNotePayload } from "@/types/library";

export default function CreateDialog({
  kind,
  close,
  create,
}: {
  kind: "folder" | "note";
  close: () => void;
  create: (value: string | CreateNotePayload) => void;
}) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-graphite/40 p-4 backdrop-blur-xs"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) close();
      }}
    >
      <div className="w-full max-w-md overflow-hidden rounded-xl border border-graphite/12 bg-paper p-5 shadow-lg">
        <header className="flex items-center justify-between border-b border-graphite/8 pb-3">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            {kind === "folder" ? (
              <FolderPlus size={18} />
            ) : (
              <StickyNote size={18} />
            )}
            {kind === "folder" ? "Create New Folder" : "Create Quick Note"}
          </h3>
          <button type="button" aria-label="Close" onClick={close}>
            <X size={14} />
          </button>
        </header>
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
          <label className="grid gap-1 text-xs font-medium text-slate">
            {kind === "folder" ? "Folder Name" : "Title"}
            <input
              autoFocus
              required
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder={
                kind === "folder" ? "e.g. Project Assets" : "Note title..."
              }
              className="h-9 rounded-md border border-graphite/14 bg-mist/40 px-3 text-xs text-graphite outline-none"
            />
          </label>
          {kind === "note" && (
            <label className="grid gap-1 text-xs font-medium text-slate">
              Content
              <textarea
                value={content}
                onChange={(event) => setContent(event.target.value)}
                rows={4}
                placeholder="Write your note content here..."
                className="rounded-md border border-graphite/14 bg-mist/40 p-3 text-xs text-graphite outline-none"
              />
            </label>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              className="rounded-md px-3 py-2 text-xs text-slate hover:bg-mist"
              onClick={close}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="rounded-md bg-graphite px-4 py-2 text-xs text-paper"
            >
              {kind === "folder" ? "Create" : "Save Note"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
