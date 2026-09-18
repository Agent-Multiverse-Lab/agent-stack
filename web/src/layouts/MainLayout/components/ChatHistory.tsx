import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useEffect, useEffectEvent, useRef, useState } from "react";
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
import { Input } from "@/components/ui/input";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { ChevronDown, MoreHorizontal } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router";
import { deleteThread, listThreads, renameThread } from "@/api/agent";
import type { ThreadSummaryResponse } from "@/types/chat";
import { useTranslation } from "@/i18n";

export default function ChatHistory() {
  const { t } = useTranslation();
  const { threadId } = useParams();
  const navigate = useNavigate();
  const { setOpenMobile } = useSidebar();
  const [expanded, setExpanded] = useState(true);
  const [threads, setThreads] = useState<ThreadSummaryResponse[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<ThreadSummaryResponse | null>(null);
  const [action, setAction] = useState<"rename" | "delete">("rename");
  const [title, setTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState("");
  const version = useRef(0);
  async function load(more = false) {
    const next = more ? cursor : undefined;
    if (more && !next) return;
    const current = ++version.current;
    setLoading(true);
    setError("");
    try {
      const result = await listThreads({
        limit: 50,
        cursor: next ?? undefined,
      });
      if (current !== version.current) return;
      setThreads((previous) =>
        more
          ? [
              ...previous,
              ...result.items.filter(
                (item) =>
                  !previous.some(
                    (existing) => existing.thread_id === item.thread_id,
                  ),
              ),
            ]
          : result.items,
      );
      setCursor(result.has_more ? result.next_cursor : null);
    } catch (cause) {
      if (current === version.current)
        setError(cause instanceof Error ? cause.message : t("Conversation loading failed"));
    } finally {
      if (current === version.current) setLoading(false);
    }
  }
  const onThreadChange = useEffectEvent(() => void load());
  useEffect(() => {
    onThreadChange();
    const requestVersion = version;
    return () => {
      requestVersion.current++;
    };
  }, [threadId]);
  function openAction(
    thread: ThreadSummaryResponse,
    nextAction: "rename" | "delete",
  ) {
    setSelected(thread);
    setAction(nextAction);
    setTitle(thread.title);
    setActionError("");
  }
  async function submit() {
    if (!selected || saving || (action === "rename" && !title.trim())) return;
    setSaving(true);
    setActionError("");
    try {
      if (action === "rename") {
        const updated = await renameThread(selected.thread_id, title.trim());
        setThreads((previous) =>
          previous.map((item) =>
            item.thread_id === selected.thread_id ? updated : item,
          ),
        );
      } else {
        await deleteThread(selected.thread_id);
        setThreads((previous) =>
          previous.filter((item) => item.thread_id !== selected.thread_id),
        );
        if (threadId === selected.thread_id) navigate("/");
      }
      setSelected(null);
    } catch (cause) {
      setActionError(
        cause instanceof Error ? cause.message : t("Operation failed. Please try again."),
      );
    } finally {
      setSaving(false);
    }
  }
  return (
    <>
      <SidebarGroup
        className="min-h-0 flex-1 px-2 pt-3 pb-1 group-data-[collapsible=icon]:hidden"
        aria-label={t("Conversation history")}
      >
        <Collapsible open={expanded} onOpenChange={setExpanded} className="flex min-h-0 flex-1 flex-col">
          <CollapsibleTrigger
            render={<Button variant="ghost" />}
            className="h-auto shrink-0 justify-start gap-1.5 rounded-sm px-2.5 py-2 text-xs font-medium text-slate hover:bg-graphite/5"
          >
            {t("Chat")}{" "}
            <ChevronDown size={13} className={expanded ? "" : "-rotate-90"} />
          </CollapsibleTrigger>
          <CollapsibleContent className="flex min-h-0 flex-1 flex-col">
          <SidebarGroupContent
            className="min-h-0 flex-1 overflow-y-auto overscroll-contain [scrollbar-width:thin]"
            aria-busy={loading}
          >
            <SidebarMenu>
              {threads.map((thread) => (
                <SidebarMenuItem key={thread.thread_id}>
                  <SidebarMenuButton
                    render={
                      <Link
                        to={`/c/${encodeURIComponent(thread.thread_id)}`}
                        onClick={() => setOpenMobile(false)}
                      />
                    }
                    isActive={threadId === thread.thread_id}
                    className="pr-9"
                    title={thread.title}
                    aria-current={threadId === thread.thread_id ? "page" : undefined}
                  >
                    <span className="block truncate">{thread.title}</span>
                  </SidebarMenuButton>
                  <DropdownMenu>
                    <DropdownMenuTrigger
                      type="button"
                      className="absolute top-1/2 right-1 grid size-7 -translate-y-1/2 place-items-center rounded-md text-slate hover:bg-sidebar-accent md:opacity-0 md:group-hover/menu-item:opacity-100 md:group-focus-within/menu-item:opacity-100"
                      aria-label={t("Conversation actions: {{title}}", { title: thread.title })}
                    >
                      <MoreHorizontal size={16} />
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => openAction(thread, "rename")}>
                        {t("Rename")}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        variant="destructive"
                        onClick={() => openAction(thread, "delete")}
                      >
                        {t("Delete conversation")}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
            {error && (
              <>
                <p role="alert" className="px-2.5 py-2 text-xs text-danger">
                  {error}
                </p>
                <Button variant="ghost"
                  type="button"
                  className="px-2.5 py-2 text-xs hover:underline"
                  onClick={() => void load(Boolean(cursor))}
                >
                  {t("Retry")}
                </Button>
              </>
            )}
            {!error && loading && (
              <p role="status" className="px-2.5 py-2 text-xs text-slate">
                {t("Loading…")}
              </p>
            )}
            {!error && !loading && !threads.length && (
              <p className="px-2.5 py-2 text-xs text-slate">{t("No conversations")}</p>
            )}
            {cursor && !loading && !error && (
              <Button variant="ghost"
                type="button"
                className="w-full rounded-sm px-2.5 py-2 text-left text-xs text-slate hover:bg-graphite/5"
                onClick={() => void load(true)}
              >
                {t("Load more")}
              </Button>
            )}
          </SidebarGroupContent>
          </CollapsibleContent>
        </Collapsible>
      </SidebarGroup>
      <Dialog
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open && !saving) setSelected(null);
        }}
      >
        <DialogContent showCloseButton={!saving}>
          <DialogHeader>
            <DialogTitle>{action === "rename" ? t("Rename conversation") : t("Delete conversation")}</DialogTitle>
            <DialogDescription
              className={action === "rename" ? "sr-only" : "break-words"}
            >
              {action === "rename"
                ? t("Enter a new conversation title")
                : t("Delete {{title}}? This conversation will be removed from your history.", { title: selected?.title })}
            </DialogDescription>
          </DialogHeader>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void submit();
            }}
          >
            {action === "rename" && (
              <Input
                autoFocus
                value={title}
                aria-label={t("Conversation title")}
                disabled={saving}
                onChange={(event) => setTitle(event.target.value)}
              />
            )}
            {actionError && (
              <p role="alert" className="mt-2 text-sm text-danger">
                {actionError}
              </p>
            )}
            <DialogFooter className="mt-4 border-0 bg-transparent p-0">
              <Button variant="ghost"
                type="button"
                disabled={saving}
                onClick={() => setSelected(null)}
                className="rounded-md px-3 py-2 text-sm hover:bg-mist disabled:opacity-50"
              >
                {t("Cancel")}
              </Button>
              <Button variant="default"
                type="submit"
                disabled={saving || (action === "rename" && !title.trim())}
                className={`rounded-md px-4 py-2 text-sm text-white disabled:opacity-50 ${action === "delete" ? "bg-danger" : "bg-graphite"}`}
              >
                {saving ? t("Processing...") : action === "rename" ? t("Save") : t("Delete")}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
