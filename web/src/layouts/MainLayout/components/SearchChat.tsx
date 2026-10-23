import { useCallback, useRef, useState } from "react";
import { Loader2, MessageSquare, Search, X } from "lucide-react";
import { useNavigate } from "react-router";
import { listThreads } from "@/api/thread";
import type { ThreadMetadataResponse } from "@/api/thread";
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
  const [threads, setThreads] = useState<ThreadMetadataResponse[]>([]);
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
      if (request.current !== current) return;
      setThreads([]);
      setCursor(null);
    } finally {
      if (request.current === current) {
        setLoading(false);
        setLoadingMore(false);
      }
    }
  }, [query]);

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) close();
      }}
    >
      <DialogContent
        showCloseButton={false}
        overlayClassName="z-[100]"
        className="z-[101] w-[640px] max-w-[90vw] gap-0 overflow-hidden rounded-2xl bg-popover p-0 text-foreground"
      >
        <DialogHeader className="sr-only">
          <DialogTitle>{t("Search conversation threads")}</DialogTitle>
          <DialogDescription>
            {t("Search and open a conversation thread.")}
          </DialogDescription>
        </DialogHeader>
        <div className="flex h-14 items-center gap-3 border-b border-border px-4">
          <Search className="size-5 shrink-0 text-muted-foreground" />
          <Input
            ref={input}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void fetchPage();
            }}
            placeholder={t("Search conversations")}
            aria-label={t("Search conversation")}
            className="h-full flex-1 border-0 bg-transparent text-base shadow-none focus-visible:ring-0"
          />
          {query && (
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label={t("Clear search")}
              onClick={() => {
                setQuery("");
                input.current?.focus();
              }}
            >
              <X size={16} />
            </Button>
          )}
          <DialogClose
            render={<Button variant="ghost" size="icon-sm" />}
            aria-label={t("Close")}
          >
            <X size={18} />
          </DialogClose>
        </div>
        <div className="max-h-[380px] min-h-[160px] overflow-y-auto overscroll-contain p-2">
          {loading ? (
            <div className="flex h-32 items-center justify-center gap-2 text-muted-foreground">
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
