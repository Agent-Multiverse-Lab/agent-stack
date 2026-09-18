import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useRef, useState } from "react";
import type { CSSProperties } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  FileText,
  Files,
  Globe,
  Map,
  MessagesSquare,
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  PanelsTopLeft,
  Plus,
  Presentation,
  Search,
} from "lucide-react";
import type { KnowledgeFileItem } from "@/types/knowledge";
import { useTranslation } from "@/i18n";

const supported = new Set([
  "pdf",
  "doc",
  "docx",
  "txt",
  "md",
  "markdown",
  "csv",
  "xls",
  "xlsx",
  "ppt",
  "pptx",
  "png",
  "jpg",
  "jpeg",
  "webp",
]);
export default function KnowledgePage() {
  const { t } = useTranslation();
  const [files, setFiles] = useState<KnowledgeFileItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [confirmRemove, setConfirmRemove] = useState<KnowledgeFileItem | null>(
    null,
  );
  const [filesCollapsed, setFilesCollapsed] = useState(false);
  const [toolsCollapsed, setToolsCollapsed] = useState(false);
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [draft, setDraft] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const visible = files.filter((file) =>
    file.name.toLowerCase().includes(appliedQuery.toLowerCase()),
  );

  function addFiles(selected: File[]) {
    const keys = new Set(
      files.map((file) => `${file.name}:${file.size}:${file.lastModified}`),
    );
    const additions = selected
      .filter((file) => {
        const key = `${file.name}:${file.size}:${file.lastModified}`;
        if (keys.has(key)) return false;
        keys.add(key);
        return true;
      })
      .filter((file) => {
        const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
        if (!supported.has(extension)) {
          toast.warning(t("{{file}} is not a supported source type.", { file: file.name }));
          return false;
        }
        return true;
      })
      .map((file) => ({
        id: crypto.randomUUID(),
        source: file,
        name: file.name,
        size: file.size,
        mimeType: file.type,
        extension: file.name.split(".").pop()?.toUpperCase() || "FILE",
        lastModified: file.lastModified,
        status: "selected" as const,
      }));
    if (!additions.length) return;
    setFiles((previous) => [...previous, ...additions]);
    setSelectedId((previous) => previous ?? additions[0].id);
  }
  function removeFile(id: string) {
    const index = files.findIndex((file) => file.id === id);
    const remaining = files.filter((file) => file.id !== id);
    setFiles(remaining);
    if (selectedId === id)
      setSelectedId(remaining[index]?.id ?? remaining[index - 1]?.id ?? null);
  }
  function openFile(file: KnowledgeFileItem, download: boolean) {
    const url = URL.createObjectURL(file.source);
    if (download) {
      const link = document.createElement("a");
      link.href = url;
      link.download = file.name;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    } else {
      window.open(url, "_blank", "noopener,noreferrer");
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    }
  }
  const columns = filesCollapsed
    ? toolsCollapsed
      ? "56px minmax(0,1fr) 56px"
      : "56px minmax(0,1.92fr) minmax(0,1fr)"
    : toolsCollapsed
      ? "minmax(0,1fr) minmax(0,1.92fr) 56px"
      : "minmax(0,1fr) minmax(0,1.92fr) minmax(0,1fr)";
  return (
    <div className="@container relative flex h-full w-full gap-2.5 overflow-hidden bg-mist p-2.5 font-sans text-graphite">
      <div className="relative flex min-w-0 flex-1 flex-col overflow-hidden rounded-[20px] border border-graphite/10 bg-paper shadow-sm">
        <header className="flex min-h-[46px] shrink-0 items-center border-b border-graphite/6 px-4 py-1.5">
          <span className="text-xs font-medium uppercase tracking-wider text-slate/80">
            {t("Knowledge Base")}
          </span>
        </header>
        <main
          className="knowledge-workspace grid min-h-0 min-w-0 w-full flex-1 gap-3 overflow-hidden bg-mist p-3 text-sm [grid-template-columns:var(--knowledge-columns)] [grid-template-rows:minmax(0,1fr)] @max-[720px]:grid-cols-1 @max-[720px]:grid-rows-none @max-[720px]:overflow-y-auto"
          style={{
            "--knowledge-columns": columns,
            transition: "grid-template-columns 240ms ease",
          } as CSSProperties}
        >
          <section className="knowledge-files grid min-h-0 min-w-0 overflow-hidden rounded-[16px] border border-graphite/10 bg-paper [grid-template-rows:48px_minmax(0,1fr)] @max-[720px]:min-h-[calc(100dvh-92px)]">
            <header className="flex h-12 items-center justify-between border-b border-graphite/6 px-3">
              <h2
                className={
                  filesCollapsed
                    ? "overflow-hidden opacity-0 @max-[720px]:opacity-100"
                    : "font-semibold"
                }
              >
                {t("Files")}
              </h2>
              <Button variant="ghost"
                type="button"
                aria-label={filesCollapsed ? t("Expand files") : t("Collapse files")}
                aria-expanded={!filesCollapsed}
                aria-controls="knowledge-files-body"
                onClick={() => setFilesCollapsed(!filesCollapsed)}
                className="grid size-10 shrink-0 place-items-center text-slate @max-[720px]:hidden"
              >
                {filesCollapsed ? (
                  <PanelLeftOpen size={18} />
                ) : (
                  <PanelLeftClose size={18} />
                )}
              </Button>
            </header>
            <div
              id="knowledge-files-body"
              className={`grid min-h-0 gap-3 overflow-hidden p-4 [grid-template-rows:auto_auto_minmax(0,1fr)] ${filesCollapsed ? "invisible opacity-0 @max-[720px]:visible @max-[720px]:opacity-100" : ""}`}
            >
              <Input
                ref={fileInput}
                type="file"
                multiple
                accept=".pdf,.doc,.docx,.txt,.md,.markdown,.csv,.xls,.xlsx,.ppt,.pptx,.png,.jpg,.jpeg,.webp"
                className="hidden"
                onChange={(event) => {
                  addFiles(Array.from(event.target.files ?? []));
                  event.target.value = "";
                }}
              />
              <Button variant="ghost"
                type="button"
                className="h-auto justify-start gap-3 text-left font-semibold"
                onClick={() => fileInput.current?.click()}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  addFiles(Array.from(event.dataTransfer.files));
                }}
              >
                <span className="grid size-9 place-items-center rounded-[16px] border border-graphite/10">
                  <Plus size={18} />
                </span>
                {t("Add Sources")}
              </Button>
              <form
                role="search"
                className="grid gap-1 rounded-[16px] border border-graphite/16 p-[0.45rem]"
                onSubmit={(event) => {
                  event.preventDefault();
                  setAppliedQuery(query.trim());
                }}
              >
                <Input
                  value={query}
                  onChange={(event) => {
                    setQuery(event.target.value);
                    if (!event.target.value.trim()) setAppliedQuery("");
                  }}
                  aria-label={t("Search files")}
                  placeholder={t("Search files")}
                  className="min-w-0 bg-transparent px-2 py-1 outline-none"
                />
                <div className="flex justify-between">
                  <Globe size={18} className="text-slate" />
                  <Button variant="default"
                    type="submit"
                    aria-label={t("Search")}
                    className="grid size-8 place-items-center rounded-full bg-graphite text-paper"
                  >
                    <Search size={18} />
                  </Button>
                </div>
              </form>
              <div className="min-h-0 overflow-y-auto">
                {visible.length ? (
                  <ul className="grid gap-1">
                    {visible.map((file) => (
                      <li
                        key={file.id}
                        className={`flex min-h-14 min-w-0 items-center gap-1 rounded-[16px] border px-2 hover:bg-mist ${selectedId === file.id ? "border-graphite/16 bg-graphite/6" : "border-transparent"}`}
                      >
                        <Button variant="ghost"
                          type="button"
                          className="h-auto min-w-0 flex-1 justify-start gap-2 text-left"
                          aria-current={
                            selectedId === file.id ? "true" : undefined
                          }
                          onClick={() => setSelectedId(file.id)}
                        >
                          <FileText size={17} />
                          <span className="truncate" title={file.name}>
                            {file.name}
                          </span>
                        </Button>
                        <DropdownMenu>
                          <DropdownMenuTrigger
                            aria-label={t("Open file actions")}
                            title={t("File actions")}
                            className="grid size-11 place-items-center text-slate"
                          >
                            <MoreHorizontal size={17} />
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={() => openFile(file, false)}
                            >
                              {t("Open file")}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => openFile(file, true)}
                            >
                              {t("Download a copy")}
                            </DropdownMenuItem>
                            <DropdownMenuItem disabled>{t("Rename")}</DropdownMenuItem>
                            <DropdownMenuItem disabled>{t("Parse file")}</DropdownMenuItem>
                            <DropdownMenuItem disabled>{t("Build index")}</DropdownMenuItem>
                            <DropdownMenuItem
                              variant="destructive"
                              onClick={() => setConfirmRemove(file)}
                            >
                              {t("Remove from list")}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="grid min-h-48 place-content-center justify-items-center gap-2 text-slate">
                    <Files size={25} />
                    {t("No files")}
                  </div>
                )}
              </div>
            </div>
          </section>
          <section
            className="grid min-h-0 min-w-0 overflow-hidden rounded-[16px] border border-graphite/10 bg-paper [grid-template-rows:48px_minmax(0,1fr)_auto] @max-[720px]:min-h-[calc(100dvh-92px)]"
            aria-labelledby="knowledge-chat-title"
          >
            <header className="flex h-12 items-center border-b border-graphite/6 px-4">
              <h1 id="knowledge-chat-title" className="text-base font-semibold">
                {t("Knowledge Chat")}
              </h1>
            </header>
            <div className="grid min-h-0 place-content-center justify-items-center gap-3 overflow-y-auto bg-mist text-slate">
              <MessagesSquare size={28} />
              <strong className="text-graphite">
                {files.length ? t("No indexed files") : t("Add a file to start")}
              </strong>
            </div>
            <form
              className="border-t border-graphite/6 p-[0.8rem]"
              onSubmit={(event) => {
                event.preventDefault();
                if (
                  draft.trim() &&
                  files.some((file) => file.status === "indexed")
                )
                  setDraft("");
              }}
            >
              <div className="flex items-center gap-2 rounded-[16px] border border-graphite/16 bg-mist px-3 py-2">
                <Textarea
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (
                      event.key === "Enter" &&
                      !event.shiftKey &&
                      !event.nativeEvent.isComposing
                    ) {
                      event.preventDefault();
                      event.currentTarget.form?.requestSubmit();
                    }
                  }}
                  disabled={!files.some((file) => file.status === "indexed")}
                  placeholder={t("Ask a question")}
                  aria-label={t("Ask this knowledge base")}
                  rows={1}
                  className="min-h-0 min-w-0 flex-1 resize-none border-0 bg-transparent px-0 py-0 focus-visible:ring-0"
                />
                <Button variant="default"
                  type="submit"
                  aria-label={t("Send question")}
                  disabled={
                    !draft.trim() ||
                    !files.some((file) => file.status === "indexed")
                  }
                  className="grid size-11 place-items-center rounded-full bg-graphite text-paper disabled:bg-graphite/10 disabled:text-graphite/58"
                >
                  ↑
                </Button>
              </div>
            </form>
          </section>
          <section className="knowledge-actions grid min-h-0 min-w-0 overflow-hidden rounded-[16px] border border-graphite/10 bg-paper [grid-template-rows:48px_minmax(0,1fr)] @max-[720px]:min-h-[calc(100dvh-92px)]">
            <header className="flex h-12 items-center justify-between border-b border-graphite/10 px-3">
              <h2
                className={
                  toolsCollapsed
                    ? "overflow-hidden opacity-0 @max-[720px]:opacity-100"
                    : "font-semibold"
                }
              >
                {t("Tools")}
              </h2>
              <Button variant="ghost"
                type="button"
                aria-label={toolsCollapsed ? t("Expand tools") : t("Collapse tools")}
                aria-expanded={!toolsCollapsed}
                aria-controls="knowledge-actions-body"
                onClick={() => setToolsCollapsed(!toolsCollapsed)}
                className="grid size-10 shrink-0 place-items-center text-slate @max-[720px]:hidden"
              >
                {toolsCollapsed ? (
                  <PanelRightOpen size={18} />
                ) : (
                  <PanelRightClose size={18} />
                )}
              </Button>
            </header>
            <div
              id="knowledge-actions-body"
              className={`grid min-h-0 [grid-template-rows:repeat(2,minmax(0,1fr))] ${toolsCollapsed ? "invisible opacity-0 @max-[720px]:visible @max-[720px]:opacity-100" : ""}`}
            >
              <div className="grid min-h-0 content-start gap-2 overflow-y-auto p-4 [grid-template-columns:repeat(auto-fit,minmax(min(100%,104px),1fr))] [grid-auto-rows:74px]">
                {[
                  { label: "Road Map", icon: Map, color: "bg-[#edf4ff] hover:bg-[#e2edff]" },
                  { label: "PPT", icon: Presentation, color: "bg-[#fff1e8] hover:bg-[#ffe7d8]" },
                  {
                    label: "Slides",
                    icon: PanelsTopLeft,
                    color: "bg-[#f3efff] hover:bg-[#eae3ff]",
                  },
                ].map(({ label, icon: Icon, color }) => (
                  <Button variant="ghost"
                    key={label}
                    type="button"
                    className={`flex h-[74px] flex-col justify-center gap-1 rounded-[16px] px-3 text-left font-medium ${color}`}
                    onClick={() => toast.info(t("{{tool}} is not connected yet.", { tool: t(label) }))}
                  >
                    <Icon size={18} />
                    {t(label)}
                  </Button>
                ))}
              </div>
              <div className="border-t border-graphite/10" />
            </div>
          </section>
        </main>
      </div>
      <Dialog
        open={confirmRemove !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmRemove(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("Remove this file?")}</DialogTitle>
            <DialogDescription>
              {t("{{file}} will be removed from this list.", { file: confirmRemove?.name })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="destructive"
              type="button"
              className="rounded-md px-3 py-2 text-sm hover:bg-mist"
              onClick={() => setConfirmRemove(null)}
            >
              {t("Keep file")}
            </Button>
            <Button variant="ghost"
              type="button"
              className="rounded-md bg-destructive px-3 py-2 text-sm text-white"
              onClick={() => {
                if (confirmRemove) removeFile(confirmRemove.id);
                setConfirmRemove(null);
              }}
            >
              {t("Remove")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
