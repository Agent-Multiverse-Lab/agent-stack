import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, RefreshCw, Search, X } from "lucide-react";
import type { PanelImperativeHandle } from "react-resizable-panels";

import { listThreads } from "@/api/thread";
import { listSandboxWorkspace } from "@/api/sandbox";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { Spinner } from "@/components/ui/spinner";
import { useTranslation } from "@/i18n";
import WorkspaceFileList from "@/pages/sandbox/components/WorkspaceFileList";
import WorkspaceFileDialog from "@/pages/sandbox/components/WorkspaceFileDialog";
import WorkspacePreview from "@/pages/sandbox/components/WorkspacePreview";
import WorkspaceTree from "@/pages/sandbox/components/WorkspaceTree";
import type { WorkspaceEntry, WorkspaceTreeNode } from "@/pages/sandbox/types";

function buildTree(entriesByPath: Record<string, WorkspaceEntry[]>): WorkspaceTreeNode[] {
  const buildNode = (name: string, path: string): WorkspaceTreeNode => ({
    name, path,
    children: (entriesByPath[path] ?? [])
      .filter((entry) => entry.kind === "directory")
      .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }))
      .map((entry) => buildNode(entry.name, entry.path)),
  });
  return [buildNode("workspace", "/workspace")];
}

export default function SandboxPage() {
  const { t } = useTranslation();
  const [threadId, setThreadId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    void listThreads({ limit: 100 }).then((response) => {
      if (!active) return;
      setThreadId(response.items[0]?.thread_id ?? "");
    }).catch((caught: unknown) => {
      if (active) setError(caught instanceof Error ? caught.message : t("Request failed"));
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [revision, t]);

  if (loading) {
    return (
      <main aria-label={t("Sandbox")} className="flex h-full min-h-0 w-full min-w-0 flex-col overflow-hidden bg-background text-foreground">
        <header className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-card px-(--page-padding)">
          <h2 className="text-sm font-medium">{t("Workspace")}</h2>
        </header>
        <div className="grid min-h-0 flex-1 place-items-center" role="status" aria-label={t("Loading...")}><Spinner /></div>
      </main>
    );
  }
  if (error || !threadId) {
    return (
      <main aria-label={t("Sandbox")} className="flex h-full min-h-0 w-full min-w-0 flex-col overflow-hidden bg-background text-foreground">
        <header className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-card px-(--page-padding)">
          <h2 className="text-sm font-medium">{t("Workspace")}</h2>
          <Button variant="ghost" size="icon-sm" aria-label={t("Refresh workspace")} onClick={() => setRevision((value) => value + 1)}><RefreshCw /></Button>
        </header>
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
          <p role={error ? "alert" : "status"}>{error || t("No conversations")}</p>
        </div>
      </main>
    );
  }
  return <SandboxWorkspace key={threadId} threadId={threadId} />;
}

function SandboxWorkspace({ threadId }: { threadId: string }) {
  const { t } = useTranslation();
  const [currentPath, setCurrentPath] = useState("/workspace");
  const [entriesByPath, setEntriesByPath] = useState<Record<string, WorkspaceEntry[]>>({});
  const [selectedEntry, setSelectedEntry] = useState<WorkspaceEntry | null>(null);
  const [editing, setEditing] = useState(false);
  const [fileAction, setFileAction] = useState<{ entry: WorkspaceEntry; action: "rename" | "delete" } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [query, setQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const previewPanel = useRef<PanelImperativeHandle>(null);
  const previewContainer = useRef<HTMLDivElement>(null);
  const returnFocus = useRef<HTMLElement>(null);
  const previewOpen = selectedEntry !== null;

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    void listSandboxWorkspace(threadId, currentPath).then((response) => {
      if (!active) return;
      const entries: WorkspaceEntry[] = response.entries.map((entry) => ({
        name: entry.name, path: entry.path, kind: entry.kind,
        size: entry.size, modifiedAt: entry.modified_at, fileType: entry.file_type ?? undefined,
      }));
      setEntriesByPath((previous) => ({ ...previous, [currentPath]: entries }));
    }).catch((caught: unknown) => {
      if (active) setError(caught instanceof Error ? caught.message : t("Request failed"));
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [currentPath, revision, threadId, t]);

  useEffect(() => {
    // Wait for the panel group to register the updated size constraints.
    const frame = requestAnimationFrame(() => {
      if (previewOpen) previewPanel.current?.resize(expanded ? "100%" : "44%");
      else previewPanel.current?.collapse();
    });
    return () => cancelAnimationFrame(frame);
  }, [previewOpen, expanded]);

  const nodes = useMemo(() => buildTree(entriesByPath), [entriesByPath]);
  function closePreview() { setSelectedEntry(null); setExpanded(false); setEditing(false); }
  function openFolder(path: string) {
    closePreview();
    setQuery("");
    if (path === currentPath) setRevision((value) => value + 1);
    else { setLoading(true); setCurrentPath(path); }
  }
  const tree = <WorkspaceTree nodes={nodes} currentPath={currentPath} onSelect={openFolder} />;

  const files = (
    <section inert={expanded} aria-label={t("Workspace files")} className="flex h-full min-w-0 flex-col overflow-hidden bg-card">
      <div className="min-h-0 flex-1 overflow-auto" aria-busy={loading}>
        {loading ? <div role="status" aria-label={t("Loading...")} className="grid h-40 place-items-center"><Spinner /></div>
          : error ? <p role="alert" className="px-6 py-10 text-sm text-destructive">{error}</p>
          : <WorkspaceFileList entries={entriesByPath[currentPath] ?? []} selectedPath={selectedEntry?.path ?? null}
              query={query} onOpenFolder={openFolder} onSelect={(entry) => {
                returnFocus.current = document.activeElement as HTMLElement;
                setEditing(false);
                setSelectedEntry(entry);
              }} onAction={(entry, action) => {
                if (action === "edit") {
                  returnFocus.current = document.activeElement as HTMLElement;
                  setSelectedEntry(entry);
                  setEditing(true);
                } else setFileAction({ entry, action });
              }} />}
      </div>
    </section>
  );

  return (
    <main aria-label={t("Sandbox")} className="flex h-full min-h-0 w-full min-w-0 flex-col overflow-hidden bg-background text-foreground">
      <header className="flex h-12 shrink-0 items-center justify-between gap-4 border-b border-border bg-card px-(--page-padding)">
        <div className="flex min-w-0 items-center gap-2.5">
          <h2 className="shrink-0 text-sm font-medium">{t("Workspace")}</h2>
          {currentPath !== "/workspace" && (
            <>
              <span aria-hidden="true" className="text-border">/</span>
              <Button variant="ghost" size="icon-sm" className="rounded-md" aria-label={t("Go to parent folder")}
                onClick={() => openFolder(currentPath.slice(0, currentPath.lastIndexOf("/")) || "/workspace")}><ArrowLeft /></Button>
              <span className="min-w-0 truncate text-sm font-medium text-muted-foreground">
                {currentPath.split("/").at(-1)}
              </span>
            </>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {searchOpen && (
            <Input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} aria-label={t("Filter this folder")}
              className="h-8 w-52 rounded-md bg-background shadow-none"
              onKeyDown={(event) => { if (event.key === "Escape") { setQuery(""); setSearchOpen(false); } }} />
          )}
          <Button variant="ghost" size="icon-sm" className="rounded-md" aria-label={t(searchOpen ? "Close search" : "Filter this folder")}
            aria-expanded={searchOpen} onClick={() => { setSearchOpen(!searchOpen); setQuery(""); }}>
            {searchOpen ? <X /> : <Search />}
          </Button>
          <Button variant="ghost" size="icon-sm" className="rounded-md" disabled={loading}
            aria-label={t("Refresh workspace")} onClick={() => setRevision((value) => value + 1)}>
            <RefreshCw className={loading ? "animate-spin motion-reduce:animate-none" : undefined} />
          </Button>
        </div>
      </header>

      <section aria-label={t("Workspace")} className="flex min-h-0 min-w-0 flex-1 overflow-hidden">
        <aside className="flex shrink-0 flex-col border-r border-border bg-card">
          <div className="min-h-0 flex-1 overflow-hidden">
            {tree}
          </div>
        </aside>
        <ResizablePanelGroup orientation="horizontal" className="min-h-0 min-w-0 flex-1">
          <ResizablePanel id="sandbox-files" defaultSize="100%" minSize={expanded ? "0%" : "240px"}>
            {files}
          </ResizablePanel>
          <ResizableHandle aria-label={t("Resize preview")} disabled={!previewOpen || expanded}
            className={previewOpen && !expanded
              ? "w-1 bg-transparent after:bg-transparent before:h-8 before:w-0.5 before:rounded-full before:bg-border"
              : "hidden"} />
          <ResizablePanel id="sandbox-preview" panelRef={previewPanel} defaultSize="0%" collapsedSize="0%"
            minSize="280px" maxSize={expanded ? "100%" : "70%"} collapsible={!previewOpen}>
            <div ref={previewContainer} className="relative h-full min-w-0 overflow-hidden bg-card" />
          </ResizablePanel>
        </ResizablePanelGroup>
        <WorkspacePreview threadId={threadId} entry={selectedEntry} container={previewContainer}
          editing={editing} onEditingChange={setEditing} onSaved={() => setRevision((value) => value + 1)}
          expanded={expanded} onExpand={() => setExpanded((value) => !value)}
          onClose={closePreview} returnFocus={returnFocus} />
        {fileAction && <WorkspaceFileDialog key={`${fileAction.action}:${fileAction.entry.path}`}
          threadId={threadId} entry={fileAction.entry} action={fileAction.action}
          onClose={() => setFileAction(null)} onComplete={(path) => {
            if (selectedEntry?.path === fileAction.entry.path) {
              if (path) {
                setSelectedEntry({ ...selectedEntry, path, name: path.split("/").at(-1)! });
                setEditing(false);
              } else closePreview();
            }
            setFileAction(null);
            setRevision((value) => value + 1);
          }} />}
      </section>
    </main>
  );
}
