import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, FolderTree, PanelLeft, RefreshCw, Search, SquareTerminal } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { useTranslation } from "@/i18n";
import WorkspaceFileList from "@/pages/sandbox/components/WorkspaceFileList";
import WorkspaceTree from "@/pages/sandbox/components/WorkspaceTree";
import { previewEntries, previewTree } from "@/pages/sandbox/mockData";
import type { WorkspaceEntry } from "@/pages/sandbox/types";

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

  const entries = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    const values = previewEntries[currentPath] ?? [];
    return normalized
      ? values.filter((entry) => entry.name.toLowerCase().includes(normalized))
      : values;
  }, [currentPath, query]);
  const breadcrumbs = currentPath.split("/").filter(Boolean);

  function openFolder(path: string) {
    setCurrentPath(path);
    setSelectedEntry(null);
    setQuery("");
  }

  const tree = <WorkspaceTree nodes={previewTree} currentPath={currentPath} onSelect={openFolder} />;

  return (
    <main
      className="flex h-full min-h-0 w-full bg-background px-3 pb-3 text-foreground sm:px-5 sm:pb-5"
      aria-label={t("Sandbox")}
    >
      <div className="mx-auto flex min-h-0 w-full max-w-[1180px] flex-col">
        <header className="flex shrink-0 flex-wrap items-end justify-between gap-4 px-1 pt-2 pb-5">
          <div>
            <div className="mb-2 flex items-center gap-2">
              <SquareTerminal className="size-4" strokeWidth={1.7} />
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{t("Isolated workspace")}</span>
              <Badge variant="outline" className="h-5 border-amber-500/35 bg-amber-500/8 px-2 text-[10px] font-medium text-amber-700 dark:text-amber-300">{t("Design preview")}</Badge>
            </div>
            <h1 className="text-2xl font-semibold tracking-[-0.035em]">{t("Workspace files")}</h1>
            <p className="mt-1 text-sm text-muted-foreground">{t("Artifacts created by the agent, kept inside this conversation.")}</p>
          </div>
          <div className="flex items-center gap-2 font-mono text-[11px] text-muted-foreground">
            <span className="size-1.5 rounded-full bg-amber-500" aria-hidden />
            {t("Preview data · read only")}
          </div>
        </header>

        <section className="flex min-h-0 flex-1 overflow-hidden rounded-xl border border-border/80 bg-card/40 shadow-[0_1px_0_rgba(255,255,255,0.04)]">
          <aside className="hidden w-60 shrink-0 flex-col border-r border-border/70 bg-muted/20 md:flex">
            <div className="flex h-12 items-center gap-2 px-4 font-mono text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
              <FolderTree className="size-3.5" />{t("Directory")}
            </div>
            {tree}
            <div className="border-t border-border/60 px-4 py-3 font-mono text-[10px] leading-relaxed text-muted-foreground">
              <span className="block text-foreground/70">thread-preview-01</span>
              <span>{t("Persistent workspace")}</span>
            </div>
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
                      <SheetTitle>{t("Directory")}</SheetTitle>
                      <SheetDescription>{t("Choose a workspace folder")}</SheetDescription>
                    </SheetHeader>
                    <div className="min-h-0 flex-1 pt-2">{tree}</div>
                  </SheetContent>
                </Sheet>
                <Button type="button" variant="ghost" size="icon-sm" disabled={currentPath === "/workspace"} aria-label={t("Go to parent folder")} onClick={() => openFolder(parentPath(currentPath))}>
                  <ChevronLeft />
                </Button>
                <nav aria-label={t("Workspace path")} className="flex min-w-0 items-center font-mono text-[11px]">
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

              <div className="flex items-center gap-1.5">
                <div className="relative hidden sm:block">
                  <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
                  <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t("Filter this folder")} aria-label={t("Filter this folder")} className="h-8 w-44 bg-background/70 pl-8 text-xs lg:w-56" />
                </div>
                <Button type="button" variant="ghost" size="icon-sm" disabled aria-label={t("Refresh workspace")} title={t("Connect the workspace API to refresh")}>
                  <RefreshCw />
                </Button>
              </div>
            </div>

            <div className="border-b border-border/60 px-3 py-2 sm:hidden">
              <div className="relative">
                <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t("Filter this folder")} aria-label={t("Filter this folder")} className="h-8 bg-background/70 pl-8 text-xs" />
              </div>
            </div>

            <div className="min-h-0 flex-1 overflow-auto">
              <WorkspaceFileList
                entries={entries}
                selectedPath={selectedEntry?.path ?? null}
                onSelect={setSelectedEntry}
                onOpenFolder={openFolder}
                labels={{ name: t("NAME"), modified: t("MODIFIED"), size: t("SIZE"), empty: t("This folder is empty") }}
              />
            </div>

            <footer className="flex h-9 shrink-0 items-center justify-between border-t border-border/60 px-4 font-mono text-[10px] text-muted-foreground">
              <span>{t("{{count}} items", { count: entries.length })}</span>
              <span className="max-w-[55%] truncate">{selectedEntry?.path ?? currentPath}</span>
            </footer>
          </div>
        </section>
      </div>
    </main>
  );
}
