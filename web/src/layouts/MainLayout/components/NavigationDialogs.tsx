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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useIsMobile } from "@/hooks/use-mobile";
import SettingsModels from "@/layouts/MainLayout/components/SettingsModels";
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
        overlayClassName="z-[100] bg-graphite/36"
        className="top-[10dvh] z-[101] flex h-[min(60vh,620px)] w-[min(84vw,980px)] max-w-[980px] translate-y-0 flex-col gap-0 overflow-hidden rounded-2xl bg-paper p-0 text-graphite shadow-2xl sm:max-w-[980px]"
      >
        <DialogTitle className="sr-only">{t("Search conversation threads")}</DialogTitle>
        <DialogDescription className="sr-only">
          {t("Search and open a conversation thread.")}
        </DialogDescription>
        <div className="flex items-center gap-4 border-b border-graphite/10 px-6 py-5">
          <Search className="h-6 w-6 shrink-0 text-slate" />
          <Input
            ref={input}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="h-auto w-full border-0 bg-transparent px-0 py-0 text-lg text-graphite placeholder:text-slate/60 focus-visible:ring-0"
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
            <div className="flex items-center justify-center gap-2 py-16 text-slate">
              <Loader2 className="animate-spin" size={20} />
              {t("Searching conversations...")}
            </div>
          ) : threads.length === 0 ? (
            <div className="py-16 text-center text-slate">
              {t("No matching conversation titles found.")}
            </div>
          ) : (
            <div className="grid gap-1.5">
              {threads.map((item) => (
                <Button
                  key={item.thread_id}
                  type="button"
                  variant="ghost"
                  className="h-auto w-full justify-start gap-3.5 rounded-xl px-4 py-3.5 text-left text-base hover:bg-mist"
                  onClick={() => {
                    close();
                    navigate(`/c/${encodeURIComponent(item.thread_id)}`);
                  }}
                >
                  <MessageSquare className="h-5 w-5 shrink-0 text-slate/70" />
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
                    className="gap-2 rounded-md text-xs text-slate hover:bg-mist"
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
        overlayClassName="z-[100] bg-graphite/36"
        className="z-[101] w-full max-w-none gap-0 overflow-hidden rounded-t-lg bg-paper p-0 text-graphite max-[767px]:top-auto max-[767px]:bottom-0 max-[767px]:translate-y-0 max-[767px]:rounded-b-none min-[768px]:max-w-[440px]"
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
          <div className="grid justify-items-center gap-3 border-b border-graphite/6 pb-6 text-center">
            <Avatar className="size-14" aria-hidden="true">
              <AvatarFallback className="bg-graphite font-utility text-lg font-bold text-paper">
                A
              </AvatarFallback>
            </Avatar>
            <div>
              <p className="font-semibold">{t("AM User")}</p>
              <p className="text-sm text-slate">
                {user?.email ?? t("Loading account…")}
              </p>
            </div>
          </div>
          <dl className="grid text-sm">
            <div className="flex justify-between border-b border-graphite/6 py-3">
              <dt>{t("Email")}</dt>
              <dd className="text-slate">{user?.email ?? "—"}</dd>
            </div>
            <div className="flex justify-between py-3">
              <dt>{t("Status")}</dt>
              <dd className="text-slate">
                {user ? (user.is_active ? t("Active") : t("Inactive")) : t("Loading")}
              </dd>
            </div>
          </dl>
        </div>
      </DialogContent>
    </Dialog>
  );
}

type Section = "general" | "account" | "models" | "data" | "about";
export function SettingsDialog({
  open,
  close,
  user,
}: {
  open: boolean;
  close: () => void;
  user: UserResponse | null;
}) {
  const { t, i18n } = useTranslation();
  const isMobile = useIsMobile();
  const [section, setSection] = useState<Section>("general");
  const [theme, setTheme] = useState("light");
  const [followUps, setFollowUps] = useState(true);
  const [improveModel, setImproveModel] = useState(false);
  useEffect(() => {
    if (open) setSection("general");
  }, [open]);
  const sections: { id: Section; name: string }[] = [
    { id: "general", name: t("General") },
    { id: "account", name: t("Account") },
    { id: "models", name: t("Models") },
    { id: "data", name: t("Data Controls") },
    { id: "about", name: t("About") },
  ];
  const row = (label: string, value: React.ReactNode) => (
    <div className="flex min-h-12 items-center justify-between gap-5 border-b border-graphite/6 py-3 text-sm">
      <span>{label}</span>
      {value}
    </div>
  );
  const toggle = (
    label: string,
    value: boolean,
    set: (value: boolean) => void,
  ) => (
    <Switch aria-label={label} checked={value} onCheckedChange={set} />
  );
  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) close();
      }}
    >
      <DialogContent
        showCloseButton={false}
        overlayClassName="z-[100] bg-graphite/36"
        className={`z-[101] flex h-[min(92dvh,760px)] w-full max-w-none flex-col gap-0 overflow-hidden rounded-t-lg bg-paper p-0 text-graphite max-[767px]:top-auto max-[767px]:bottom-0 max-[767px]:translate-y-0 max-[767px]:rounded-b-none ${section === "models" ? "min-[768px]:max-w-[1120px]" : "min-[768px]:max-w-[860px]"}`}
      >
        <DialogHeader className="flex min-h-[3.25rem] flex-row items-center justify-between px-5">
          <DialogTitle id="settings-title" className="text-[0.95rem] font-semibold">
            {t("Settings")}
          </DialogTitle>
          <DialogClose
            render={<Button variant="ghost" size="icon-sm" />}
            aria-label={t("Close settings")}
          >
            <X size={19} />
          </DialogClose>
        </DialogHeader>
        <DialogDescription className="sr-only">
          {t("Application settings.")}
        </DialogDescription>
        <Tabs
          value={section}
          onValueChange={(value) => setSection(value as Section)}
          orientation={isMobile ? "horizontal" : "vertical"}
          className="grid min-h-0 flex-1 [grid-template-rows:auto_minmax(0,1fr)] min-[768px]:grid-rows-1 min-[768px]:grid-cols-[168px_minmax(0,1fr)]"
        >
          <TabsList
            className="flex w-full flex-row justify-start gap-0.5 overflow-x-auto bg-transparent px-3 py-2 min-[768px]:flex-col min-[768px]:items-stretch"
            aria-label={t("Settings sections")}
          >
            {sections.map((item) => (
              <TabsTrigger
                key={item.id}
                value={item.id}
                className={`min-h-9 shrink-0 rounded-sm px-2.5 text-left text-sm ${section === item.id ? "bg-graphite/5 font-semibold" : "text-slate"}`}
              >
                {item.name}
              </TabsTrigger>
            ))}
          </TabsList>
          <div
            className="min-h-0 overflow-y-auto px-4 pt-4 pb-6 min-[768px]:px-7"
            aria-live="polite"
          >
            <TabsContent
              value={section}
              className="h-full"
            >
              <h3 className="mb-5 text-base font-semibold">
                {sections.find((item) => item.id === section)?.name}
              </h3>
              {section === "models" ? (
                <SettingsModels />
              ) : section === "general" ? (
                <>
                  {row(
                    t("Theme"),
                    <Select
                      value={theme}
                      onValueChange={(value) => setTheme(value ?? "light")}
                    >
                      <SelectTrigger id="settings-theme" aria-label={t("Theme")} className="bg-transparent text-slate">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="light">{t("Light")}</SelectItem>
                        <SelectItem value="system">{t("System")}</SelectItem>
                        <SelectItem value="dark">{t("Dark")}</SelectItem>
                      </SelectContent>
                    </Select>,
                  )}
                  {row(
                    t("Language"),
                    <Select
                      value={i18n.resolvedLanguage === "zh-CN" ? "zh-CN" : "en"}
                      onValueChange={(value) => {
                        if (value) void i18n.changeLanguage(value);
                      }}
                    >
                      <SelectTrigger id="settings-language" aria-label={t("Language")} className="bg-transparent text-slate">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="en">English</SelectItem>
                        <SelectItem value="zh-CN">简体中文</SelectItem>
                      </SelectContent>
                    </Select>,
                  )}
                  {row(
                    t("Show follow-up suggestions"),
                    toggle(
                      t("Show follow-up suggestions"),
                      followUps,
                      setFollowUps,
                    ),
                  )}
                </>
              ) : section === "account" ? (
                <>
                  {row(
                    t("Status"),
                    user
                      ? user.is_active
                        ? t("Active")
                        : t("Inactive")
                      : t("Not logged in"),
                  )}
                  {row(t("Account"), user?.email ?? "—")}
                </>
              ) : section === "data" ? (
                row(
                  t("Improve the model"),
                  toggle(t("Improve the model"), improveModel, setImproveModel),
                )
              ) : (
                <>
                  {row(t("Product"), "AM")}
                  {row(t("Version"), t("Preview"))}
                </>
              )}
            </TabsContent>
          </div>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
