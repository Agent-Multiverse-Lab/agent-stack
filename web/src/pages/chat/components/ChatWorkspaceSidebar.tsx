import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowLeft,
  Bot,
  CheckCircle2,
  Circle,
  Download,
  FileText,
  Folder,
  Folders,
  Loader2,
  Maximize2,
  Minimize2,
  PanelRight,
  RefreshCw,
  Search,
  Sparkles,
  X,
} from "lucide-react";

import type { ThreadMessageAttachmentResponse } from "@/api/attachment";
import {
  downloadSandboxFile,
  listSandboxWorkspace,
  readSandboxFile,
} from "@/api/sandbox";
import { FileContentViewer } from "@/components/common/file-content-viewer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useTranslation } from "@/i18n";
import {
  buildArtifactItems,
  extractArtifactsFromMessages,
  formatArtifactSize,
  type PresentedArtifact,
} from "@/pages/chat/artifacts";
import type { ChatMessage } from "@/pages/chat/types";

export type ChatSidebarTab = "state" | "files";

interface TodoItem {
  content: string;
  status: "pending" | "in_progress" | "completed";
}

interface WorkspaceEntryItem {
  name: string;
  path: string;
  kind: "directory" | "file";
  size: number | null;
  modifiedAt: string;
}

interface ChatWorkspaceSidebarProps {
  open: boolean;
  tab: ChatSidebarTab;
  onTabChange: (tab: ChatSidebarTab) => void;
  onClose: () => void;
  threadId?: string;
  agentId?: string;
  modelId?: string;
  runId: string | null;
  runStatus: string | null;
  statusLabel: string;
  statusDotClass: string;
  active: boolean;
  messages: ChatMessage[];
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const isAttachment = (
  value: unknown,
): value is ThreadMessageAttachmentResponse =>
  isRecord(value) && typeof value.file_id === "string";

function extractLatestTodos(messages: ChatMessage[]): TodoItem[] {
  let latest: TodoItem[] = [];
  for (const message of messages) {
    const event = isRecord(message.payload.event) ? message.payload.event : {};
    const state = isRecord(event.agent_state) ? event.agent_state : {};
    if (!Array.isArray(state.agent_todo)) continue;
    const parsed = state.agent_todo.filter(
      (item): item is TodoItem =>
        isRecord(item) &&
        typeof item.content === "string" &&
        (item.status === "pending" ||
          item.status === "in_progress" ||
          item.status === "completed"),
    );
    if (parsed.length > 0) {
      latest = parsed;
    }
  }
  return latest;
}

function extractConversationAttachments(
  messages: ChatMessage[],
): ThreadMessageAttachmentResponse[] {
  const seen = new Set<string>();
  const list: ThreadMessageAttachmentResponse[] = [];
  for (const message of messages) {
    const event = isRecord(message.payload.event) ? message.payload.event : {};
    if (!Array.isArray(event.attachments)) continue;
    for (const item of event.attachments) {
      if (!isAttachment(item) || seen.has(item.file_id)) continue;
      seen.add(item.file_id);
      list.push(item);
    }
  }
  return list;
}

export function ChatWorkspaceSidebar({
  open,
  tab,
  onTabChange,
  onClose,
  threadId,
  agentId,
  modelId,
  runId,
  statusLabel,
  statusDotClass,
  active,
  messages,
}: ChatWorkspaceSidebarProps) {
  const { t } = useTranslation();
  const [maximized, setMaximized] = useState(false);
  const [currentPath, setCurrentPath] = useState("/workspace");
  const [entries, setEntries] = useState<WorkspaceEntryItem[]>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [filesError, setFilesError] = useState("");
  const [revision, setRevision] = useState(0);
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [previewFile, setPreviewFile] = useState<{
    name: string;
    path: string;
    content: string;
    loading: boolean;
    error: string;
    truncated: boolean;
  } | null>(null);

  useEffect(() => {
    setCurrentPath("/workspace");
    setEntries([]);
    setFilesError("");
    setPreviewFile(null);
    setQuery("");
    setSearchOpen(false);
  }, [threadId]);

  useEffect(() => {
    if (!open || tab !== "files" || !threadId) return;
    let mounted = true;
    setLoadingFiles(true);
    setFilesError("");
    void Promise.resolve(listSandboxWorkspace(threadId, currentPath))
      .then((response) => {
        if (!mounted) return;
        const mapped: WorkspaceEntryItem[] = Array.isArray(response?.entries)
          ? response.entries.map((entry) => ({
              name: entry.name,
              path: entry.path,
              kind: entry.kind,
              size: entry.size,
              modifiedAt: entry.modified_at,
            }))
          : [];
        setEntries(mapped);
      })
      .catch((caught: unknown) => {
        if (mounted) {
          setFilesError(
            caught instanceof Error ? caught.message : t("Request failed"),
          );
        }
      })
      .finally(() => {
        if (mounted) setLoadingFiles(false);
      });

    return () => {
      mounted = false;
    };
  }, [currentPath, open, revision, tab, threadId, t]);

  useEffect(() => {
    if (!open || !previewFile?.path || !threadId) return;
    let mounted = true;
    const targetPath = previewFile.path;
    void Promise.resolve(readSandboxFile(threadId, targetPath))
      .then((response) => {
        if (!mounted) return;
        setPreviewFile((current) =>
          current && current.path === targetPath
            ? {
                ...current,
                content: response.content,
                loading: false,
                error: "",
                truncated: response.truncated,
              }
            : current,
        );
      })
      .catch((caught: unknown) => {
        if (!mounted) return;
        setPreviewFile((current) =>
          current && current.path === targetPath
            ? {
                ...current,
                content: "",
                loading: false,
                error:
                  caught instanceof Error
                    ? caught.message
                    : t("Unable to preview file"),
                truncated: false,
              }
            : current,
        );
      });
    return () => {
      mounted = false;
    };
  }, [open, previewFile?.path, threadId, t]);

  const todos = useMemo(() => extractLatestTodos(messages), [messages]);
  const completedTodos = useMemo(
    () => todos.filter((item) => item.status === "completed").length,
    [todos],
  );
  const todoProgressPercent =
    todos.length > 0 ? Math.round((completedTodos / todos.length) * 100) : 0;

  const artifacts = useMemo(
    () => buildArtifactItems(extractArtifactsFromMessages(messages, threadId)),
    [messages, threadId],
  );
  const conversationAttachments = useMemo(
    () => extractConversationAttachments(messages),
    [messages],
  );

  const filteredEntries = useMemo(() => {
    const trimmed = query.trim().toLowerCase();
    if (!trimmed) return entries;
    return entries.filter((entry) =>
      entry.name.toLowerCase().includes(trimmed),
    );
  }, [entries, query]);

  if (!open) return null;

  const openFilePreview = (name: string, path: string) => {
    onTabChange("files");
    setPreviewFile({
      name,
      path,
      content: "",
      loading: true,
      error: "",
      truncated: false,
    });
  };

  const handleDownloadFile = async (path: string, name: string) => {
    if (!threadId) return;
    try {
      const blob = await downloadSandboxFile(threadId, path);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = name;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      // Ignore download errors in quick action
    }
  };

  const handleArtifactClick = (artifact: PresentedArtifact) => {
    if (artifact.status !== "generated") return;
    openFilePreview(artifact.name, artifact.path);
  };

  return (
    <aside
      aria-label={t("Workspace sidebar")}
      className={`flex h-full min-h-0 shrink-0 flex-col border-l border-border bg-card text-card-foreground transition-[width] duration-200 motion-reduce:transition-none ${
        maximized ? "w-full" : "w-[380px]"
      }`}
    >
      <Tabs
        value={tab}
        onValueChange={(value) => onTabChange(value as ChatSidebarTab)}
        className="flex h-full min-h-0 flex-1 flex-col gap-0"
      >
        <div className="flex h-12 shrink-0 items-center justify-between gap-2 border-b border-border px-3">
          <TabsList className="h-8 gap-1 bg-muted/60 p-0.5">
            <TabsTrigger
              value="state"
              className="h-7 gap-1.5 rounded-md px-2.5 text-xs font-medium"
            >
              <Activity className="size-3.5" />
              <span>{t("Agent state")}</span>
            </TabsTrigger>
            <TabsTrigger
              value="files"
              className="h-7 gap-1.5 rounded-md px-2.5 text-xs font-medium"
            >
              <Folders className="size-3.5" />
              <span>{t("Workspace files")}</span>
            </TabsTrigger>
          </TabsList>

          <div className="flex shrink-0 items-center gap-1">
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label={t(
                maximized ? "Restore preview width" : "Expand preview",
              )}
              title={t(maximized ? "Restore preview width" : "Expand preview")}
              onClick={() => setMaximized((current) => !current)}
            >
              {maximized ? (
                <Minimize2 className="size-4" />
              ) : (
                <Maximize2 className="size-4" />
              )}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label={t("Close workspace")}
              title={t("Close workspace")}
              onClick={onClose}
            >
              <PanelRight className="size-4" />
            </Button>
          </div>
        </div>

        <TabsContent
          value="state"
          className="m-0 flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto bg-muted/20 p-3"
        >
          <Card size="sm" className="[--card-spacing:--spacing(3)]">
            <CardHeader>
              <div className="flex min-w-0 items-center gap-2.5">
                <span className="grid size-8 shrink-0 place-items-center rounded-lg border border-border bg-secondary text-secondary-foreground">
                  <Bot className="size-4" aria-hidden="true" />
                </span>
                <div className="min-w-0">
                  <CardTitle className="truncate text-xs">
                    {agentId || "LeaderAgent"}
                  </CardTitle>
                  <CardDescription className="truncate text-[11px]">
                    {modelId || t("Models")}
                  </CardDescription>
                </div>
              </div>
              <CardAction>
                <Badge variant="outline" className="gap-1.5 text-[11px]">
                  <span
                    aria-hidden="true"
                    className={`size-1.5 rounded-full ${statusDotClass}`}
                  />
                  <span>{statusLabel}</span>
                </Badge>
              </CardAction>
            </CardHeader>
            {runId && (
              <CardContent className="border-t border-border/60 pt-2.5">
                <div className="flex items-center justify-between gap-2 text-xs">
                  <span className="shrink-0 text-muted-foreground">Run ID</span>
                  <span className="truncate font-mono text-[11px] text-muted-foreground">
                    {runId}
                  </span>
                </div>
              </CardContent>
            )}
          </Card>

          <Card size="sm" className="[--card-spacing:--spacing(3)]">
            <CardHeader>
              <CardTitle className="text-xs">
                {t("Execution process")}
              </CardTitle>
              <CardDescription className="text-[11px]">
                {todos.length > 0
                  ? t("{{completed}} completed", { completed: completedTodos })
                  : active
                    ? t("Working")
                    : t("No active tasks")}
              </CardDescription>
              {todos.length > 0 && (
                <CardAction>
                  <Badge variant="outline" className="tabular-nums text-[11px]">
                    {completedTodos}/{todos.length}
                  </Badge>
                </CardAction>
              )}
            </CardHeader>
            {todos.length > 0 && (
              <CardContent className="flex flex-col gap-2">
                <div
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={todoProgressPercent}
                  className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
                >
                  <div
                    className="h-full rounded-full bg-primary transition-[width] duration-200"
                    style={{ width: `${todoProgressPercent}%` }}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  {todos.map((todo, index) => (
                    <Card
                      key={`${todo.content}-${index}`}
                      size="sm"
                      className="flex-row items-start justify-between gap-2 bg-muted/20 py-2 [--card-spacing:--spacing(2.5)]"
                    >
                      <div className="flex min-w-0 items-start gap-2 px-2.5 text-xs">
                        {todo.status === "completed" ? (
                          <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-success" />
                        ) : todo.status === "in_progress" ? (
                          <Loader2 className="mt-0.5 size-3.5 shrink-0 animate-spin text-primary motion-reduce:animate-none" />
                        ) : (
                          <Circle className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
                        )}
                        <span
                          className={
                            todo.status === "completed"
                              ? "text-muted-foreground line-through"
                              : "font-medium text-foreground"
                          }
                        >
                          {todo.content}
                        </span>
                      </div>
                    </Card>
                  ))}
                </div>
              </CardContent>
            )}
          </Card>

          {artifacts.length > 0 && (
            <Card size="sm" className="[--card-spacing:--spacing(3)]">
              <CardHeader>
                <CardTitle className="text-xs">{t("Generated")}</CardTitle>
                <CardAction>
                  <Badge variant="outline" className="tabular-nums text-[11px]">
                    {artifacts.length}
                  </Badge>
                </CardAction>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {artifacts.map((artifact) => (
                  <Card
                    key={artifact.path}
                    size="sm"
                    className="py-2 [--card-spacing:--spacing(2.5)] hover:bg-muted/40"
                  >
                    <CardContent className="flex items-center justify-between gap-2">
                      <Button
                        type="button"
                        variant="ghost"
                        disabled={artifact.status !== "generated"}
                        onClick={() => handleArtifactClick(artifact)}
                        className="flex h-auto min-w-0 flex-1 items-center justify-start gap-2.5 p-0 text-left text-xs font-normal hover:bg-transparent"
                      >
                        <span className="grid size-7 shrink-0 place-items-center rounded-md border border-border bg-secondary/60 text-primary">
                          <Sparkles className="size-3.5" />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-medium text-foreground">
                            {artifact.name}
                          </span>
                          <span className="block truncate font-mono text-[11px] text-muted-foreground">
                            {artifact.path}
                          </span>
                        </span>
                      </Button>
                      <Badge variant="outline" className="shrink-0 text-[11px]">
                        {artifact.status === "generated"
                          ? t("Completed")
                          : artifact.status === "failed"
                            ? t("Failed")
                            : t("In progress")}
                      </Badge>
                    </CardContent>
                  </Card>
                ))}
              </CardContent>
            </Card>
          )}

          {conversationAttachments.length > 0 && (
            <Card size="sm" className="[--card-spacing:--spacing(3)]">
              <CardHeader>
                <CardTitle className="text-xs">{t("Files")}</CardTitle>
                <CardAction>
                  <Badge variant="outline" className="tabular-nums text-[11px]">
                    {conversationAttachments.length}
                  </Badge>
                </CardAction>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {conversationAttachments.map((file) => (
                  <Card
                    key={file.file_id}
                    size="sm"
                    className="bg-muted/20 py-2 [--card-spacing:--spacing(2.5)]"
                  >
                    <CardContent className="flex items-center justify-between gap-2 text-xs">
                      <span className="flex min-w-0 items-center gap-2">
                        <span className="grid size-7 shrink-0 place-items-center rounded-md border border-border bg-card text-muted-foreground">
                          <FileText className="size-3.5" />
                        </span>
                        <span className="truncate font-medium text-foreground">
                          {file.file_name}
                        </span>
                      </span>
                      <span className="shrink-0 text-[11px] text-muted-foreground">
                        {formatArtifactSize(file.file_size)}
                      </span>
                    </CardContent>
                  </Card>
                ))}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent
          value="files"
          className="m-0 flex min-h-0 flex-1 flex-col gap-3 overflow-hidden bg-muted/20 p-3"
        >
          {previewFile ? (
            <Card
              size="sm"
              className="flex min-h-0 flex-1 flex-col gap-0 overflow-hidden py-0 [--card-spacing:--spacing(3)]"
            >
              <CardHeader className="flex flex-row items-center justify-between gap-2 border-b border-border py-2.5">
                <div className="flex min-w-0 items-center gap-1.5">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label={t("Back to list")}
                    onClick={() => setPreviewFile(null)}
                  >
                    <ArrowLeft className="size-4" />
                  </Button>
                  <div className="min-w-0">
                    <CardTitle className="truncate text-xs">
                      {previewFile.name}
                    </CardTitle>
                    <CardDescription className="truncate font-mono text-[11px]">
                      {previewFile.path}
                    </CardDescription>
                  </div>
                </div>
                <CardAction>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label={t("Download")}
                    title={t("Download")}
                    onClick={() =>
                      void handleDownloadFile(
                        previewFile.path,
                        previewFile.name,
                      )
                    }
                  >
                    <Download className="size-4" />
                  </Button>
                </CardAction>
              </CardHeader>
              <CardContent className="min-h-0 flex-1 overflow-auto p-0">
                <FileContentViewer
                  path={previewFile.path}
                  content={previewFile.content}
                  loading={previewFile.loading}
                  error={previewFile.error}
                  truncated={previewFile.truncated}
                />
              </CardContent>
            </Card>
          ) : (
            <>
              <Card
                size="sm"
                className="shrink-0 gap-2 py-2.5 [--card-spacing:--spacing(3)]"
              >
                <CardContent className="flex flex-col gap-2">
                  <div className="flex items-center justify-between gap-1.5">
                    <div className="flex min-w-0 items-center gap-1.5">
                      {currentPath !== "/workspace" && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-sm"
                          aria-label={t("Go to parent folder")}
                          onClick={() =>
                            setCurrentPath(
                              currentPath.slice(
                                0,
                                currentPath.lastIndexOf("/"),
                              ) || "/workspace",
                            )
                          }
                        >
                          <ArrowLeft className="size-3.5" />
                        </Button>
                      )}
                      <span className="truncate font-mono text-xs font-medium text-foreground">
                        {currentPath}
                      </span>
                    </div>

                    <div className="flex shrink-0 items-center gap-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        disabled={!threadId}
                        aria-label={t(
                          searchOpen ? "Close search" : "Filter this folder",
                        )}
                        onClick={() => {
                          setSearchOpen((current) => !current);
                          setQuery("");
                        }}
                      >
                        {searchOpen ? (
                          <X className="size-3.5" />
                        ) : (
                          <Search className="size-3.5" />
                        )}
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        disabled={!threadId || loadingFiles}
                        aria-label={t("Refresh workspace")}
                        onClick={() => setRevision((value) => value + 1)}
                      >
                        <RefreshCw
                          className={`size-3.5 ${
                            loadingFiles
                              ? "animate-spin motion-reduce:animate-none"
                              : ""
                          }`}
                        />
                      </Button>
                    </div>
                  </div>

                  {searchOpen && (
                    <Input
                      autoFocus
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      placeholder={t("Search files")}
                      aria-label={t("Filter this folder")}
                      className="h-7 text-xs"
                    />
                  )}
                </CardContent>
              </Card>

              <div className="min-h-0 flex-1 overflow-y-auto">
                {!threadId ? (
                  <Card size="sm" className="[--card-spacing:--spacing(4)]">
                    <CardContent className="py-6 text-center text-xs text-muted-foreground">
                      {t("Start a conversation to view workspace files")}
                    </CardContent>
                  </Card>
                ) : loadingFiles ? (
                  <Card size="sm" className="[--card-spacing:--spacing(4)]">
                    <CardContent
                      role="status"
                      aria-label={t("Loading...")}
                      className="grid h-36 place-items-center"
                    >
                      <Spinner />
                    </CardContent>
                  </Card>
                ) : filesError ? (
                  <Card size="sm" className="[--card-spacing:--spacing(4)]">
                    <CardContent
                      role="alert"
                      className="py-4 text-center text-xs text-destructive"
                    >
                      {filesError}
                    </CardContent>
                  </Card>
                ) : filteredEntries.length === 0 ? (
                  <Card size="sm" className="[--card-spacing:--spacing(4)]">
                    <CardContent className="py-6 text-center text-xs text-muted-foreground">
                      {query.trim()
                        ? t("No matching files")
                        : t("This folder is empty")}
                    </CardContent>
                  </Card>
                ) : (
                  <div className="flex flex-col gap-2">
                    {filteredEntries.map((entry) => (
                      <Card
                        key={entry.path}
                        size="sm"
                        className="group py-2 [--card-spacing:--spacing(2.5)] hover:border-input hover:bg-muted/40"
                      >
                        <CardContent className="flex items-center justify-between gap-2">
                          <Button
                            type="button"
                            variant="ghost"
                            onClick={() => {
                              if (entry.kind === "directory") {
                                setCurrentPath(entry.path);
                                setQuery("");
                              } else {
                                openFilePreview(entry.name, entry.path);
                              }
                            }}
                            className="flex h-auto min-w-0 flex-1 items-center justify-start gap-2.5 p-0 text-left text-xs font-normal hover:bg-transparent"
                          >
                            <span className="grid size-8 shrink-0 place-items-center rounded-md border border-border bg-secondary/50">
                              {entry.kind === "directory" ? (
                                <Folder className="size-4 text-primary" />
                              ) : (
                                <FileText className="size-4 text-muted-foreground" />
                              )}
                            </span>
                            <span className="min-w-0 flex-1">
                              <span className="block truncate font-medium text-foreground">
                                {entry.name}
                              </span>
                              <span className="block truncate text-[11px] text-muted-foreground">
                                {entry.kind === "directory"
                                  ? t("Directory")
                                  : formatArtifactSize(entry.size) || t("Files")}
                              </span>
                            </span>
                          </Button>
                          {entry.kind === "file" && (
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon-sm"
                              aria-label={`${t("Download")} ${entry.name}`}
                              title={t("Download")}
                              onClick={() =>
                                void handleDownloadFile(entry.path, entry.name)
                              }
                              className="size-7 shrink-0"
                            >
                              <Download className="size-3.5" />
                            </Button>
                          )}
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </TabsContent>
      </Tabs>
    </aside>
  );
}
