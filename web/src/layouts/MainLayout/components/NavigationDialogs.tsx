import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, MessageSquare, Search, X } from "lucide-react";
import { useNavigate } from "react-router";
import { listThreads } from "@/api/agent";
import type { ThreadSummaryResponse } from "@/types/chat";
import type { UserResponse } from "@/types/auth";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useTranslation } from "@/i18n";

export function SearchChat({
  open,
  close,
}: {
  open: boolean;
  close: () => void;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [threads, setThreads] = useState<ThreadSummaryResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [cursor, setCursor] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const request = useRef(0);
  const fetchPage = useCallback(async (nextCursor?: string) => {
    const current = ++request.current;
    if (nextCursor) setLoadingMore(true);
    else setLoading(true);
    try {
      const result = await listThreads({
        query: query.trim() || undefined,
        cursor: nextCursor,
        limit: 15,
      });
      if (request.current !== current) return;
      setThreads((previous) =>
        nextCursor ? [...previous, ...result.items] : result.items,
      );
      setCursor(result.has_more ? result.next_cursor : null);
    } catch {
      if (request.current === current && !nextCursor) setThreads([]);
    } finally {
      if (request.current === current) {
        setLoading(false);
        setLoadingMore(false);
      }
    }
  }, [query]);
  useEffect(() => {
    if (!open) {
      setQuery("");
      setThreads([]);
      setCursor(null);
      request.current++;
      return;
    }
    input.current?.focus();
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const timer = setTimeout(
      () => {
        void fetchPage();
      },
      query ? 250 : 0,
    );
    return () => clearTimeout(timer);
  }, [open, fetchPage, query]);
  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) close();
      }}
    >
      <DialogContent
        showCloseButton={false}
        overlayClassName="z-[100] bg-primary/36"
        className="top-[10dvh] z-[101] flex h-[min(60vh,620px)] w-[min(84vw,980px)] max-w-[980px] translate-y-0 flex-col gap-0 overflow-hidden rounded-2xl bg-background p-0 text-foreground shadow-2xl sm:max-w-[980px]"
      >
        <DialogTitle className="sr-only">{t("Search conversation threads")}</DialogTitle>
        <DialogDescription className="sr-only">
          {t("Search and open a conversation thread.")}
        </DialogDescription>
        <div className="flex items-center gap-4 border-b border-border px-6 py-5">
          <Search className="h-6 w-6 shrink-0 text-muted-foreground" />
          <Input
            ref={input}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="h-auto w-full border-0 bg-transparent px-0 py-0 text-lg text-foreground placeholder:text-muted-foreground focus-visible:ring-0"
            placeholder={t("Search conversation")}
          />
          {query && (
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label={t("Clear search")}
              onClick={() => setQuery("")}
            >
              <X size={20} />
            </Button>
          )}
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground">
              <Loader2 className="animate-spin" size={20} />
              {t("Searching conversations...")}
            </div>
          ) : threads.length === 0 ? (
            <div className="py-16 text-center text-muted-foreground">
              {t("No matching conversation titles found.")}
            </div>
          ) : (
            <div className="grid gap-1.5">
              {threads.map((item) => (
                <Button
                  key={item.thread_id}
                  type="button"
                  variant="ghost"
                  className="h-auto w-full justify-start gap-3.5 rounded-xl px-4 py-3.5 text-left text-base hover:bg-accent"
                  onClick={() => {
                    close();
                    navigate(`/c/${encodeURIComponent(item.thread_id)}`);
                  }}
                >
                  <MessageSquare className="h-5 w-5 shrink-0 text-muted-foreground" />
                  <span className="truncate font-medium">
                    {item.title || t("Untitled Conversation")}
                  </span>
                </Button>
              ))}
              {cursor && (
                <div className="pt-2 text-center">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={loadingMore}
                    className="gap-2 rounded-md text-xs text-muted-foreground hover:bg-accent"
                    onClick={() => void fetchPage(cursor)}
                  >
                    {loadingMore
                      ? t("Loading more...")
                      : t("Load more conversations")}
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function ProfileDialog({
  open,
  close,
  user,
}: {
  open: boolean;
  close: () => void;
  user: UserResponse | null;
}) {
  const { t } = useTranslation();
  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) close();
      }}
    >
      <DialogContent
        showCloseButton={false}
        overlayClassName="z-[100] bg-primary/36"
        className="z-[101] w-full max-w-none gap-0 overflow-hidden rounded-t-lg bg-background p-0 text-foreground max-[767px]:top-auto max-[767px]:bottom-0 max-[767px]:translate-y-0 max-[767px]:rounded-b-none min-[768px]:max-w-[440px]"
      >
        <DialogHeader className="flex min-h-[3.25rem] flex-row items-center justify-between px-5">
          <DialogTitle id="profile-title" className="text-[0.95rem] font-semibold">
            {t("Profile")}
          </DialogTitle>
          <DialogClose
            render={<Button variant="ghost" size="icon-sm" />}
            aria-label={t("Close profile")}
          >
            <X size={19} />
          </DialogClose>
        </DialogHeader>
        <DialogDescription className="sr-only">
          {t("Your account details.")}
        </DialogDescription>
        <div className="grid gap-6 px-5 pt-3 pb-6">
          <div className="grid justify-items-center gap-3 border-b border-border pb-6 text-center">
            <Avatar className="size-14" aria-hidden="true">
              <AvatarFallback className="bg-primary font-mono text-lg font-bold text-primary-foreground">
                A
              </AvatarFallback>
            </Avatar>
            <div>
              <p className="font-semibold">{t("AM User")}</p>
              <p className="text-sm text-muted-foreground">
                {user?.email ?? t("Loading account…")}
              </p>
            </div>
          </div>
          <dl className="grid text-sm">
            <div className="flex justify-between border-b border-border py-3">
              <dt>{t("Email")}</dt>
              <dd className="text-muted-foreground">{user?.email ?? "—"}</dd>
            </div>
            <div className="flex justify-between py-3">
              <dt>{t("Status")}</dt>
              <dd className="text-muted-foreground">
                {user ? (user.is_active ? t("Active") : t("Inactive")) : t("Loading")}
              </dd>
            </div>
          </dl>
        </div>
      </DialogContent>
    </Dialog>
  );
}
