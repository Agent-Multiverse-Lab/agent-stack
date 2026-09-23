import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, PanelLeft, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FileContentViewer } from "@/components/common/file-content-viewer";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { listThreads } from "@/api/agent";
import { listSandboxWorkspace, readSandboxFile } from "@/api/sandbox";
import { useTranslation } from "@/i18n";
import WorkspaceFileList from "@/pages/sandbox/components/WorkspaceFileList";
import WorkspaceTree from "@/pages/sandbox/components/WorkspaceTree";
import type { WorkspaceEntry, WorkspaceTreeNode } from "@/pages/sandbox/types";

function buildTree(entriesByPath: Record<string, WorkspaceEntry[]>): WorkspaceTreeNode[] {
  const buildNode = (name: string, path: string): WorkspaceTreeNode => ({
    name,
    path,
    children: (entriesByPath[path] ?? [])
      .filter((entry) => entry.kind === "directory")
      .map((entry) => buildNode(entry.name, entry.path)),
  });
  return [buildNode("workspace", "/workspace")];
}

function parentPath(path: string) {
  const parts = path.split("/").filter(Boolean);
  if (parts.length <= 1) return "/workspace";
  return `/${parts.slice(0, -1).join("/")}`;
}

export default function SandboxPage() {
  const { t } = useTranslation();
  const [currentPath, setCurrentPath] = useState("/workspace");
  const [selectedEntry, setSelectedEntry] = useState<WorkspaceEntry | null>(null);
  const [query, setQuery] = useState("");
  const [threadId, setThreadId] = useState("");
  const [entriesByPath, setEntriesByPath] = useState<Record<string, WorkspaceEntry[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [fileContent, setFileContent] = useState("");
  const [fileContentTruncated, setFileContentTruncated] = useState(false);
  const [fileLoading, setFileLoading] = useState(false);
  const [fileError, setFileError] = useState("");

  useEffect(() => {
    let active = true;
    void listThreads({ limit: 100 })
      .then((response) => {
        if (!active) return;
        setThreadId((current) => current || response.items[0]?.thread_id || "");
        if (!response.items.length) setLoading(false);
      })
      .catch((caught: unknown) => {
        if (!active) return;
        setError(caught instanceof Error ? caught.message : t("Request failed"));
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [t]);

  const mapEntries = useCallback(
    (entries: Awaited<ReturnType<typeof listSandboxWorkspace>>["entries"]): WorkspaceEntry[] =>
      entries.map((entry) => ({
        name: entry.name,
        path: entry.path,
        kind: entry.kind,
        size: entry.size,
        modifiedAt: entry.modified_at,
        fileType: entry.file_type ?? undefined,
      })),
    [],
  );

  const loadPath = useCallback(async (nextPath: string, refresh = false) => {
    if (!threadId) return;
    if (!refresh && entriesByPath[nextPath]) return;
    setLoading(true);
    setError("");
    try {
      const response = await listSandboxWorkspace(threadId, nextPath);
      setEntriesByPath((previous) => ({
        ...previous,
        [response.path]: mapEntries(response.entries),
      }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("Request failed"));
    } finally {
      setLoading(false);
    }
  }, [entriesByPath, mapEntries, threadId, t]);

  useEffect(() => {
    if (!threadId) return;
    let active = true;
    setCurrentPath("/workspace");
    setSelectedEntry(null);
    setEntriesByPath({});
    setLoading(true);
    void listSandboxWorkspace(threadId, "/workspace")
      .then((response) => {
        if (!active) return;
        setEntriesByPath({ [response.path]: mapEntries(response.entries) });
        setError("");
      })
      .catch((caught: unknown) => {
        if (active) setError(caught instanceof Error ? caught.message : t("Request failed"));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [mapEntries, threadId, t]);

  useEffect(() => {
    if (!threadId || selectedEntry?.kind !== "file") {
      setFileContent("");
      setFileContentTruncated(false);
      setFileError("");
      setFileLoading(false);
      return;
    }

    let active = true;
    setFileContent("");
    setFileContentTruncated(false);
    setFileError("");
    setFileLoading(true);
    void readSandboxFile(threadId, selectedEntry.path)
      .then((response) => {
        if (!active) return;
        setFileContent(response.content);
        setFileContentTruncated(response.truncated);
      })
      .catch((caught: unknown) => {
        if (!active) return;
        setFileError(caught instanceof Error ? caught.message : t("Request failed"));
      })
      .finally(() => {
        if (active) setFileLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedEntry, t, threadId]);

  const entries = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    const values = entriesByPath[currentPath] ?? [];
    return normalized
      ? values.filter((entry) => entry.name.toLowerCase().includes(normalized))
      : values;
  }, [currentPath, entriesByPath, query]);
  const breadcrumbs = currentPath.split("/").filter(Boolean);

  function openFolder(path: string) {
    setCurrentPath(path);
    setSelectedEntry(null);
    setQuery("");
    void loadPath(path);
  }

  const tree = <WorkspaceTree nodes={buildTree(entriesByPath)} currentPath={currentPath} onSelect={openFolder} />;

  return (
    <main
      className="flex h-full min-h-0 w-full overflow-hidden bg-background text-foreground"
      aria-label={t("Sandbox")}
    >
      <aside className="hidden w-50 shrink-0 flex-col border-r border-border/70 bg-muted/20 pt-2 md:flex">
        {tree}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex min-h-12 shrink-0 flex-wrap items-center justify-between gap-2 border-b border-border/70 px-3 py-2 sm:px-4">
          <div className="flex min-w-0 items-center gap-1">
            <Sheet>
              <SheetTrigger render={<Button type="button" variant="ghost" size="icon-sm" className="md:hidden" aria-label={t("Open directory tree")} />}>
                <PanelLeft />
              </SheetTrigger>
              <SheetContent side="left" className="gap-0 p-0">
                <SheetHeader className="border-b">
                  <SheetTitle>{t("Workspace")}</SheetTitle>
                  <SheetDescription>{t("Choose a workspace folder")}</SheetDescription>
                </SheetHeader>
                <div className="min-h-0 flex-1 pt-2">{tree}</div>
              </SheetContent>
            </Sheet>
            <Button type="button" variant="ghost" size="icon-sm" disabled={currentPath === "/workspace"} aria-label={t("Go to parent folder")} onClick={() => openFolder(parentPath(currentPath))}>
              <ChevronLeft />
            </Button>
            <nav aria-label={t("Workspace path")} className="flex min-w-0 items-center text-[11px]">
              {breadcrumbs.map((part, index) => {
                const path = `/${breadcrumbs.slice(0, index + 1).join("/")}`;
                const current = index === breadcrumbs.length - 1;
                return (
                  <span key={path} className="flex min-w-0 items-center">
                    {index > 0 ? <ChevronRight className="mx-0.5 size-3 shrink-0 text-muted-foreground/50" /> : null}
                    <Button type="button" variant="ghost" size="xs" className={current ? "text-foreground" : "text-muted-foreground"} onClick={() => openFolder(path)}>
                      <span className="max-w-32 truncate">{part}</span>
                    </Button>
                  </span>
                );
              })}
            </nav>
          </div>

          <div className="flex items-center gap-2">
            <Button type="button" variant="ghost" size="icon-sm" disabled={!threadId || loading} aria-label={t("Refresh workspace")} onClick={() => void loadPath(currentPath, true)}>
              <RefreshCw className={loading ? "animate-spin" : undefined} />
            </Button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-auto">
          <WorkspaceFileList
            entries={entries}
            selectedPath={selectedEntry?.path ?? null}
            query={query}
            emptyMessage={error || t("This folder is empty")}
            onQueryChange={setQuery}
            onSelect={setSelectedEntry}
            onOpenFolder={openFolder}
          />
        </div>
      </div>

      <Sheet
        open={selectedEntry?.kind === "file"}
        onOpenChange={(open) => {
          if (!open) setSelectedEntry(null);
        }}
      >
        <SheetContent className="w-full gap-0 sm:max-w-2xl">
          <SheetHeader className="border-b pr-12">
            <SheetTitle className="truncate">{selectedEntry?.name ?? t("File preview")}</SheetTitle>
            <SheetDescription className="truncate">
              {selectedEntry?.path ?? t("Read-only sandbox file")}
            </SheetDescription>
          </SheetHeader>
          <FileContentViewer
            key={selectedEntry?.path}
            path={selectedEntry?.path ?? ""}
            content={fileContent}
            loading={fileLoading}
            error={fileError}
            truncated={fileContentTruncated}
          />
        </SheetContent>
      </Sheet>
    </main>
  );
}
