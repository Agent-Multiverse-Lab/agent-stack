"use client"

import { useEffect, useEffectEvent, useRef, useState } from "react"
import {
  ArrowRightIcon,
  ChevronDownIcon,
  FolderIcon,
  MoreHorizontalIcon,
  Trash2Icon,
} from "lucide-react"
import { Link, useNavigate, useParams } from "react-router"

import { deleteThread, listThreads, renameThread } from "@/api/agent"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { useTranslation } from "@/i18n"
import type { ThreadSummaryResponse } from "@/types/chat"

export function NavProjects({ onSearch, query = "" }: { onSearch: () => void; query?: string }) {
  const { t } = useTranslation()
  const { threadId } = useParams()
  const navigate = useNavigate()
  const { isMobile, setOpenMobile } = useSidebar()
  const [threads, setThreads] = useState<ThreadSummaryResponse[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [selected, setSelected] = useState<ThreadSummaryResponse | null>(null)
  const [action, setAction] = useState<"rename" | "delete">("rename")
  const [title, setTitle] = useState("")
  const [saving, setSaving] = useState(false)
  const [actionError, setActionError] = useState("")
  const version = useRef(0)

  const normalizedQuery = query.trim().toLocaleLowerCase()
  const visibleThreads = normalizedQuery
    ? threads.filter((thread) =>
        thread.title.toLocaleLowerCase().includes(normalizedQuery),
      )
    : threads

  async function load(more = false) {
    const next = more ? cursor : undefined
    if (more && !next) return
    const current = ++version.current
    setLoading(true)
    setError("")
    try {
      const result = await listThreads({
        limit: 50,
        cursor: next ?? undefined,
      })
      if (current !== version.current) return
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
      )
      setCursor(result.has_more ? result.next_cursor : null)
    } catch (cause) {
      if (current === version.current) {
        setError(
          cause instanceof Error
            ? cause.message
            : t("Conversation loading failed"),
        )
      }
    } finally {
      if (current === version.current) setLoading(false)
    }
  }

  const onThreadChange = useEffectEvent(() => void load())
  useEffect(() => {
    onThreadChange()
    const requestVersion = version
    return () => {
      requestVersion.current++
    }
  }, [threadId])

  function openAction(
    thread: ThreadSummaryResponse,
    nextAction: "rename" | "delete",
  ) {
    setSelected(thread)
    setAction(nextAction)
    setTitle(thread.title)
    setActionError("")
  }

  async function submit() {
    if (!selected || saving || (action === "rename" && !title.trim())) return
    setSaving(true)
    setActionError("")
    try {
      if (action === "rename") {
        const updated = await renameThread(selected.thread_id, title.trim())
        setThreads((previous) =>
          previous.map((item) =>
            item.thread_id === selected.thread_id ? updated : item,
          ),
        )
      } else {
        await deleteThread(selected.thread_id)
        setThreads((previous) =>
          previous.filter((item) => item.thread_id !== selected.thread_id),
        )
        if (threadId === selected.thread_id) navigate("/")
      }
      setSelected(null)
    } catch (cause) {
      setActionError(
        cause instanceof Error
          ? cause.message
          : t("Operation failed. Please try again."),
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <SidebarGroup
        className="min-h-0 flex-1 pt-0 group-data-[collapsible=icon]:hidden"
        aria-label={t("Conversation history")}
      >
        <SidebarGroupLabel className="gap-1.5">
          <ChevronDownIcon />
          <span>{t("Conversations")}</span>
        </SidebarGroupLabel>
        <SidebarMenu className="min-h-0 flex-1 overflow-y-auto">
          {visibleThreads.map((item) => (
            <SidebarMenuItem key={item.thread_id}>
              <SidebarMenuButton
                render={
                  <Link
                    to={`/c/${encodeURIComponent(item.thread_id)}`}
                    onClick={() => setOpenMobile(false)}
                  />
                }
                isActive={threadId === item.thread_id}
                title={item.title}
                aria-current={
                  threadId === item.thread_id ? "page" : undefined
                }
              >
                <span>{item.title}</span>
              </SidebarMenuButton>
              <DropdownMenu>
                <DropdownMenuTrigger
                  render={
                    <SidebarMenuAction
                      showOnHover
                      className="aria-expanded:bg-muted"
                    />
                  }
                  aria-label={t("Conversation actions: {{title}}", {
                    title: item.title,
                  })}
                >
                  <MoreHorizontalIcon />
                  <span className="sr-only">{t("More")}</span>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  className="w-fit"
                  side={isMobile ? "bottom" : "right"}
                  align={isMobile ? "end" : "start"}
                >
                  <DropdownMenuItem
                    onClick={() => {
                      setOpenMobile(false)
                      navigate(`/c/${encodeURIComponent(item.thread_id)}`)
                    }}
                  >
                    <FolderIcon />
                    <span>{t("Open conversation")}</span>
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => openAction(item, "rename")}>
                    <ArrowRightIcon />
                    <span>{t("Rename")}</span>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    variant="destructive"
                    onClick={() => openAction(item, "delete")}
                  >
                    <Trash2Icon />
                    <span>{t("Delete conversation")}</span>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </SidebarMenuItem>
          ))}
          {error && (
            <SidebarMenuItem>
              <p role="alert" className="px-2 py-1 text-xs text-destructive">
                {error}
              </p>
              <Button
                variant="ghost"
                size="sm"
                type="button"
                onClick={() => void load(Boolean(cursor))}
              >
                {t("Retry")}
              </Button>
            </SidebarMenuItem>
          )}
          {!error && loading && (
            <SidebarMenuItem>
              <p role="status" className="px-2 py-1 text-xs text-muted-foreground">
                {t("Loading…")}
              </p>
            </SidebarMenuItem>
          )}
          {!error && !loading && !threads.length && (
            <SidebarMenuItem>
              <p className="px-2 py-1 text-xs text-muted-foreground">
                {t("No conversations")}
              </p>
            </SidebarMenuItem>
          )}
          {!error &&
            !loading &&
            Boolean(normalizedQuery) &&
            threads.length > 0 &&
            !visibleThreads.length && (
              <SidebarMenuItem>
                <p className="px-2 py-1 text-xs text-muted-foreground">
                  {t("No matching conversation titles found.")}
                </p>
              </SidebarMenuItem>
            )}
          {cursor && !loading && !error && (
            <SidebarMenuItem>
              <SidebarMenuButton onClick={() => void load(true)}>
                <MoreHorizontalIcon />
                <span>{t("Load more")}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          )}
          <SidebarMenuItem>
            <SidebarMenuButton
              className="text-sidebar-foreground/70"
              onClick={() => {
                setOpenMobile(false)
                onSearch()
              }}
            >
              <MoreHorizontalIcon className="text-sidebar-foreground/70" />
              <span>{t("More")}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarGroup>

      <Dialog
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open && !saving) setSelected(null)
        }}
      >
        <DialogContent showCloseButton={!saving}>
          <DialogHeader>
            <DialogTitle>
              {action === "rename"
                ? t("Rename conversation")
                : t("Delete conversation")}
            </DialogTitle>
            <DialogDescription
              className={action === "rename" ? "sr-only" : "break-words"}
            >
              {action === "rename"
                ? t("Enter a new conversation title")
                : t(
                    "Delete {{title}}? This conversation will be removed from your history.",
                    { title: selected?.title },
                  )}
            </DialogDescription>
          </DialogHeader>
          <form
            onSubmit={(event) => {
              event.preventDefault()
              void submit()
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
              <p role="alert" className="mt-2 text-sm text-destructive">
                {actionError}
              </p>
            )}
            <DialogFooter className="mt-4">
              <Button
                variant="ghost"
                type="button"
                disabled={saving}
                onClick={() => setSelected(null)}
              >
                {t("Cancel")}
              </Button>
              <Button
                variant={action === "delete" ? "destructive" : "default"}
                type="submit"
                disabled={saving || (action === "rename" && !title.trim())}
              >
                {saving
                  ? t("Processing...")
                  : action === "rename"
                    ? t("Save")
                    : t("Delete")}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}
