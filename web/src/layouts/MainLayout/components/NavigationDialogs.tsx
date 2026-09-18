import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Loader2, MessageSquare, Search, X } from "lucide-react";
import { useNavigate } from "react-router";
import { listThreads } from "@/api/agent";
import type { ThreadSummaryResponse } from "@/types/chat";
import type { UserResponse } from "@/types/auth";
import SettingsModels from "@/layouts/MainLayout/components/SettingsModels";

function useEscape(open: boolean, close: () => void) {
  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, close]);
}

export function SearchChat({
  open,
  close,
}: {
  open: boolean;
  close: () => void;
}) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [threads, setThreads] = useState<ThreadSummaryResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [cursor, setCursor] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const request = useRef(0);
  useEscape(open, close);
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
  if (!open) return null;
  return createPortal(
    <div
      className="fixed inset-0 z-[100] grid place-items-start justify-center bg-graphite/36 p-4 pt-[10dvh]"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) close();
      }}
    >
      <div
        className="flex h-[min(60vh,620px)] w-[min(84vw,980px)] max-w-[980px] flex-col overflow-hidden rounded-2xl bg-paper text-graphite shadow-2xl ring-1 ring-graphite/10"
        role="dialog"
        aria-modal="true"
        aria-label="Search conversation threads"
      >
        <div className="flex items-center gap-4 border-b border-graphite/10 px-6 py-5">
          <Search className="h-6 w-6 shrink-0 text-slate" />
          <input
            ref={input}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="w-full bg-transparent text-lg text-graphite placeholder:text-slate/60 focus:outline-none"
            placeholder="Search conversation"
          />
          {query && (
            <button
              type="button"
              aria-label="Clear search"
              onClick={() => setQuery("")}
            >
              <X size={20} />
            </button>
          )}
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-16 text-slate">
              <Loader2 className="animate-spin" size={20} />
              Searching conversations...
            </div>
          ) : threads.length === 0 ? (
            <div className="py-16 text-center text-slate">
              No matching conversation titles found.
            </div>
          ) : (
            <div className="grid gap-1.5">
              {threads.map((item) => (
                <button
                  key={item.thread_id}
                  type="button"
                  className="flex w-full items-center gap-3.5 rounded-xl px-4 py-3.5 text-left text-base hover:bg-mist"
                  onClick={() => {
                    close();
                    navigate(`/c/${encodeURIComponent(item.thread_id)}`);
                  }}
                >
                  <MessageSquare className="h-5 w-5 shrink-0 text-slate/70" />
                  <span className="truncate font-medium">
                    {item.title || "Untitled Conversation"}
                  </span>
                </button>
              ))}
              {cursor && (
                <div className="pt-2 text-center">
                  <button
                    type="button"
                    disabled={loadingMore}
                    className="inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-xs text-slate hover:bg-mist"
                    onClick={() => void fetchPage(cursor)}
                  >
                    {loadingMore
                      ? "Loading more..."
                      : "Load more conversations"}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}

function Avatar({
  label = "AM User",
  large = false,
}: {
  label?: string;
  large?: boolean;
}) {
  return (
    <span
      className={`inline-grid shrink-0 place-items-center rounded-full bg-graphite font-utility font-bold leading-none text-paper ${large ? "size-14 text-lg" : "size-7 text-[11px]"}`}
      aria-hidden="true"
    >
      {label.trim().charAt(0).toUpperCase() || "A"}
    </span>
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
  useEscape(open, close);
  if (!open) return null;
  return createPortal(
    <div
      className="fixed inset-0 z-[100] grid place-items-end bg-graphite/36 min-[640px]:place-items-center min-[640px]:p-6"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) close();
      }}
    >
      <section
        className="w-full rounded-t-lg bg-paper text-graphite min-[640px]:max-w-[440px] min-[640px]:rounded-lg"
        role="dialog"
        aria-modal="true"
        aria-labelledby="profile-title"
      >
        <header className="flex min-h-[3.25rem] items-center justify-between px-5">
          <h2 id="profile-title" className="text-[0.95rem] font-semibold">
            Profile
          </h2>
          <button type="button" aria-label="Close profile" onClick={close}>
            <X size={19} />
          </button>
        </header>
        <div className="grid gap-6 px-5 pt-3 pb-6">
          <div className="grid justify-items-center gap-3 border-b border-graphite/6 pb-6 text-center">
            <Avatar large />
            <div>
              <p className="font-semibold">AM User</p>
              <p className="text-sm text-slate">
                {user?.email ?? "Loading account…"}
              </p>
            </div>
          </div>
          <dl className="grid text-sm">
            <div className="flex justify-between border-b border-graphite/6 py-3">
              <dt>Email</dt>
              <dd className="text-slate">{user?.email ?? "—"}</dd>
            </div>
            <div className="flex justify-between py-3">
              <dt>Status</dt>
              <dd className="text-slate">
                {user ? (user.is_active ? "Active" : "Inactive") : "Loading"}
              </dd>
            </div>
          </dl>
        </div>
      </section>
    </div>,
    document.body,
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
  const [section, setSection] = useState<Section>("general");
  const [theme, setTheme] = useState("light");
  const [language, setLanguage] = useState("en");
  const [followUps, setFollowUps] = useState(true);
  const [improveModel, setImproveModel] = useState(false);
  useEscape(open, close);
  useEffect(() => {
    if (open) setSection("general");
  }, [open]);
  if (!open) return null;
  const sections: { id: Section; name: string }[] = [
    { id: "general", name: "General" },
    { id: "account", name: "Account" },
    { id: "models", name: "Models" },
    { id: "data", name: "Data Controls" },
    { id: "about", name: "About" },
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
    <button
      type="button"
      role="switch"
      aria-label={label}
      aria-checked={value}
      onClick={() => set(!value)}
      className={`relative h-6 w-10 shrink-0 rounded-full ${value ? "bg-graphite" : "bg-graphite/10"}`}
    >
      <span
        className={`absolute left-[3px] top-[3px] h-[18px] w-[18px] rounded-full bg-paper transition-transform ${value ? "translate-x-4" : ""}`}
      />
    </button>
  );
  return createPortal(
    <div
      className="fixed inset-0 z-[100] grid place-items-end bg-graphite/36 min-[768px]:place-items-center min-[768px]:p-6"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) close();
      }}
    >
      <section
        className={`flex h-[min(92dvh,760px)] w-full flex-col overflow-hidden rounded-t-lg bg-paper text-graphite min-[768px]:rounded-lg ${section === "models" ? "min-[768px]:max-w-[1120px]" : "min-[768px]:max-w-[860px]"}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
      >
        <header className="flex min-h-[3.25rem] items-center justify-between px-5">
          <h2 id="settings-title" className="text-[0.95rem] font-semibold">
            Settings
          </h2>
          <button type="button" aria-label="Close settings" onClick={close}>
            <X size={19} />
          </button>
        </header>
        <div className="grid min-h-0 flex-1 [grid-template-rows:auto_minmax(0,1fr)] min-[768px]:grid-rows-1 min-[768px]:grid-cols-[168px_minmax(0,1fr)]">
          <nav
            className="flex gap-0.5 overflow-x-auto px-3 py-2 min-[768px]:flex-col"
            aria-label="Settings sections"
            role="tablist"
          >
            {sections.map((item) => (
              <button
                key={item.id}
                id={`settings-tab-${item.id}`}
                type="button"
                role="tab"
                aria-selected={section === item.id}
                aria-controls={`settings-section-${item.id}`}
                onClick={() => setSection(item.id)}
                className={`min-h-9 shrink-0 rounded-sm px-2.5 text-left text-sm ${section === item.id ? "bg-graphite/5 font-semibold" : "text-slate"}`}
              >
                {item.name}
              </button>
            ))}
          </nav>
          <div
            className="min-h-0 overflow-y-auto px-4 pt-4 pb-6 min-[768px]:px-7"
            aria-live="polite"
          >
            <section
              id={`settings-section-${section}`}
              role="tabpanel"
              aria-labelledby={`settings-tab-${section}`}
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
                    "Theme",
                    <select
                      id="settings-theme"
                      value={theme}
                      onChange={(event) => setTheme(event.target.value)}
                      className="bg-transparent text-slate"
                    >
                      <option value="light">Light</option>
                      <option value="system">System</option>
                      <option value="dark">Dark</option>
                    </select>,
                  )}
                  {row(
                    "Language",
                    <select
                      id="settings-language"
                      value={language}
                      onChange={(event) => setLanguage(event.target.value)}
                      className="bg-transparent text-slate"
                    >
                      <option value="en">English</option>
                      <option value="zh-CN">简体中文</option>
                    </select>,
                  )}
                  {row(
                    "Show follow-up suggestions",
                    toggle(
                      "Show follow-up suggestions",
                      followUps,
                      setFollowUps,
                    ),
                  )}
                </>
              ) : section === "account" ? (
                <>
                  {row(
                    "Status",
                    user
                      ? user.is_active
                        ? "Active"
                        : "Inactive"
                      : "Not logged in",
                  )}
                  {row("Account", user?.email ?? "—")}
                </>
              ) : section === "data" ? (
                row(
                  "Improve the model",
                  toggle("Improve the model", improveModel, setImproveModel),
                )
              ) : (
                <>
                  {row("Product", "AM")}
                  {row("Version", "Preview")}
                </>
              )}
            </section>
          </div>
        </div>
      </section>
    </div>,
    document.body,
  );
}

export { Avatar };
