import { useRef, useState } from "react";
import { Dropdown, Modal, message } from "antd";
import {
  BookOpenCheck,
  Bot,
  FileText,
  Files,
  Globe,
  Layers,
  Library,
  LogIn,
  Map,
  MessagesSquare,
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  PanelsTopLeft,
  Plus,
  Presentation,
  Search,
  SquarePen,
  SquareTerminal,
} from "lucide-react";
import { Link } from "react-router";
import logoUrl from "@/assets/logo.svg";
import type { KnowledgeFileItem } from "@/types/knowledge";

const supported = new Set([
  "pdf",
  "doc",
  "docx",
  "txt",
  "md",
  "markdown",
  "csv",
  "xls",
  "xlsx",
  "ppt",
  "pptx",
  "png",
  "jpg",
  "jpeg",
  "webp",
]);
const nav = [
  { to: "/", label: "Chat", icon: SquarePen },
  { to: "/library", label: "Library", icon: Library },
  { to: "/knowledge", label: "Knowledge", icon: BookOpenCheck },
  { to: "/agent", label: "Agent", icon: Bot },
  { to: "/static", label: "Static", icon: Layers },
  { to: "/sandbox", label: "Sandbox", icon: SquareTerminal },
];

export default function KnowledgePage() {
  const [files, setFiles] = useState<KnowledgeFileItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filesCollapsed, setFilesCollapsed] = useState(false);
  const [toolsCollapsed, setToolsCollapsed] = useState(false);
  const [railHovered, setRailHovered] = useState(false);
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [draft, setDraft] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const visible = files.filter((file) =>
    file.name.toLowerCase().includes(appliedQuery.toLowerCase()),
  );

  function addFiles(selected: File[]) {
    const keys = new Set(
      files.map((file) => `${file.name}:${file.size}:${file.lastModified}`),
    );
    const additions = selected
      .filter((file) => {
        const key = `${file.name}:${file.size}:${file.lastModified}`;
        if (keys.has(key)) return false;
        keys.add(key);
        return true;
      })
      .filter((file) => {
        const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
        if (!supported.has(extension)) {
          void message.warning(`${file.name} is not a supported source type.`);
          return false;
        }
        return true;
      })
      .map((file) => ({
        id: crypto.randomUUID(),
        source: file,
        name: file.name,
        size: file.size,
        mimeType: file.type,
        extension: file.name.split(".").pop()?.toUpperCase() || "FILE",
        lastModified: file.lastModified,
        status: "selected" as const,
      }));
    if (!additions.length) return;
    setFiles((previous) => [...previous, ...additions]);
    setSelectedId((previous) => previous ?? additions[0].id);
  }
  function removeFile(id: string) {
    const index = files.findIndex((file) => file.id === id);
    const remaining = files.filter((file) => file.id !== id);
    setFiles(remaining);
    if (selectedId === id)
      setSelectedId(remaining[index]?.id ?? remaining[index - 1]?.id ?? null);
  }
  const fileMenu = (file: KnowledgeFileItem) => ({
    items: [
      { key: "open", label: "Open file" },
      { key: "download", label: "Download a copy" },
      { key: "rename", label: "Rename", disabled: true },
      { key: "parse", label: "Parse file", disabled: true },
      { key: "index", label: "Build index", disabled: true },
      { key: "remove", label: "Remove from list", danger: true },
    ],
    onClick: ({ key }: { key: string }) => {
      if (key === "remove") {
        Modal.confirm({
          title: "Remove this file?",
          content: `${file.name} will be removed from this list.`,
          okText: "Remove",
          okType: "danger",
          cancelText: "Keep file",
          centered: true,
          onOk: () => removeFile(file.id),
        });
        return;
      }
      const url = URL.createObjectURL(file.source);
      if (key === "open") {
        window.open(url, "_blank", "noopener,noreferrer");
        window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
      }
      if (key === "download") {
        const link = document.createElement("a");
        link.href = url;
        link.download = file.name;
        link.click();
        window.setTimeout(() => URL.revokeObjectURL(url), 0);
      }
    },
  });
  const columns = filesCollapsed
    ? toolsCollapsed
      ? "56px minmax(0,1fr) 56px"
      : "56px minmax(0,1.92fr) minmax(0,1fr)"
    : toolsCollapsed
      ? "minmax(0,1fr) minmax(0,1.92fr) 56px"
      : "minmax(0,1fr) minmax(0,1.92fr) minmax(0,1fr)";
  return (
    <div className="relative flex h-dvh w-full gap-2.5 overflow-hidden bg-mist p-2.5 font-sans text-graphite">
      <div
        className="relative z-30 h-full w-[56px] shrink-0 select-none"
        onMouseEnter={() => setRailHovered(true)}
        onMouseLeave={() => setRailHovered(false)}
      >
        <aside
          className={`flex h-full flex-col overflow-hidden bg-mist py-2 transition-[width] duration-250 ${railHovered ? "absolute inset-y-0 left-0 z-40 w-[220px] px-1.5 shadow-lg" : "w-[56px] items-center px-1"}`}
          aria-label="Application navigation"
        >
          <header className="mb-2 flex h-11 shrink-0 items-center gap-3 px-1.5">
            <Link
              to="/"
              className="flex items-center gap-3 font-semibold"
              aria-label="AM home"
            >
              <span className="grid size-8 shrink-0 place-items-center rounded-xl bg-graphite">
                <img src={logoUrl} alt="" className="size-4 invert" />
              </span>
              {railHovered && <span>AM</span>}
            </Link>
          </header>
          <nav
            className="grid w-full gap-1.5 pt-1 pb-2"
            aria-label="Primary navigation"
          >
            {nav.map(({ to, label, icon: Icon }) => (
              <Link
                key={to}
                to={to}
                title={label}
                className={`flex h-10 w-full items-center rounded-xl text-sm ${railHovered ? "gap-1 px-1" : "justify-center"} ${to === "/knowledge" ? "bg-graphite/10 font-semibold" : "text-slate hover:bg-graphite/6"}`}
              >
                <span className="grid size-8 place-items-center">
                  <Icon size={18} />
                </span>
                {railHovered && <span className="truncate">{label}</span>}
              </Link>
            ))}
          </nav>
          <div className="min-h-0 flex-1" />
          <footer className="w-full pt-2 pb-1">
            <Link
              to="/"
              title="Back to Home"
              className={`flex h-10 items-center rounded-xl text-sm text-slate hover:bg-graphite/6 ${railHovered ? "gap-1 px-1" : "justify-center"}`}
            >
              <span className="grid size-8 place-items-center">
                <LogIn size={18} />
              </span>
              {railHovered && "Back to Home"}
            </Link>
          </footer>
        </aside>
      </div>
      <div className="relative flex min-w-0 flex-1 flex-col overflow-hidden rounded-[20px] border border-graphite/10 bg-paper shadow-sm">
        <header className="flex min-h-[46px] shrink-0 items-center border-b border-graphite/6 px-4 py-1.5">
          <span className="text-xs font-medium uppercase tracking-wider text-slate/80">
            Knowledge Base
          </span>
        </header>
        <main
          className="knowledge-workspace grid min-h-0 min-w-0 w-full flex-1 gap-3 overflow-hidden bg-mist p-3 text-sm [grid-template-rows:minmax(0,1fr)] max-[720px]:grid-cols-[minmax(0,1fr)] max-[720px]:grid-rows-none max-[720px]:overflow-y-auto"
          style={{
            gridTemplateColumns: columns,
            transition: "grid-template-columns 240ms ease",
          }}
        >
          <section className="knowledge-files grid min-h-0 min-w-0 overflow-hidden rounded-[16px] border border-graphite/10 bg-paper [grid-template-rows:48px_minmax(0,1fr)] max-[720px]:min-h-[calc(100dvh-92px)]">
            <header className="flex h-12 items-center justify-between border-b border-graphite/6 px-3">
              <h2
                className={
                  filesCollapsed
                    ? "overflow-hidden opacity-0 max-[720px]:opacity-100"
                    : "font-semibold"
                }
              >
                Files
              </h2>
              <button
                type="button"
                aria-label={filesCollapsed ? "Expand files" : "Collapse files"}
                aria-expanded={!filesCollapsed}
                aria-controls="knowledge-files-body"
                onClick={() => setFilesCollapsed(!filesCollapsed)}
                className="grid size-10 shrink-0 place-items-center text-slate max-[720px]:hidden"
              >
                {filesCollapsed ? (
                  <PanelLeftOpen size={18} />
                ) : (
                  <PanelLeftClose size={18} />
                )}
              </button>
            </header>
            <div
              id="knowledge-files-body"
              className={`grid min-h-0 gap-3 overflow-hidden p-4 [grid-template-rows:auto_auto_minmax(0,1fr)] ${filesCollapsed ? "invisible opacity-0 max-[720px]:visible max-[720px]:opacity-100" : ""}`}
            >
              <input
                ref={fileInput}
                type="file"
                multiple
                accept=".pdf,.doc,.docx,.txt,.md,.markdown,.csv,.xls,.xlsx,.ppt,.pptx,.png,.jpg,.jpeg,.webp"
                className="hidden"
                onChange={(event) => {
                  addFiles(Array.from(event.target.files ?? []));
                  event.target.value = "";
                }}
              />
              <button
                type="button"
                className="flex items-center gap-3 text-left font-semibold"
                onClick={() => fileInput.current?.click()}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  addFiles(Array.from(event.dataTransfer.files));
                }}
              >
                <span className="grid size-9 place-items-center rounded-[16px] border border-graphite/10">
                  <Plus size={18} />
                </span>
                Add Sources
              </button>
              <form
                role="search"
                className="grid gap-1 rounded-[16px] border border-graphite/16 p-[0.45rem]"
                onSubmit={(event) => {
                  event.preventDefault();
                  setAppliedQuery(query.trim());
                }}
              >
                <input
                  value={query}
                  onChange={(event) => {
                    setQuery(event.target.value);
                    if (!event.target.value.trim()) setAppliedQuery("");
                  }}
                  aria-label="Search files"
                  placeholder="Search files"
                  className="min-w-0 bg-transparent px-2 py-1 outline-none"
                />
                <div className="flex justify-between">
                  <Globe size={18} className="text-slate" />
                  <button
                    type="submit"
                    aria-label="Search"
                    className="grid size-8 place-items-center rounded-full bg-graphite text-paper"
                  >
                    <Search size={18} />
                  </button>
                </div>
              </form>
              <div className="min-h-0 overflow-y-auto">
                {visible.length ? (
                  <ul className="grid gap-1">
                    {visible.map((file) => (
                      <li
                        key={file.id}
                        className={`flex min-h-14 min-w-0 items-center gap-1 rounded-[16px] border px-2 hover:bg-mist ${selectedId === file.id ? "border-graphite/16 bg-graphite/6" : "border-transparent"}`}
                      >
                        <button
                          type="button"
                          className="flex min-w-0 flex-1 items-center gap-2 text-left"
                          aria-current={
                            selectedId === file.id ? "true" : undefined
                          }
                          onClick={() => setSelectedId(file.id)}
                        >
                          <FileText size={17} />
                          <span className="truncate" title={file.name}>
                            {file.name}
                          </span>
                        </button>
                        <Dropdown
                          trigger={["click"]}
                          placement="bottomRight"
                          menu={fileMenu(file)}
                        >
                          <button
                            type="button"
                            aria-label="Open file actions"
                            title="File actions"
                            className="grid size-11 place-items-center text-slate"
                          >
                            <MoreHorizontal size={17} />
                          </button>
                        </Dropdown>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="grid min-h-48 place-content-center justify-items-center gap-2 text-slate">
                    <Files size={25} />
                    No files
                  </div>
                )}
              </div>
            </div>
          </section>
          <section
            className="grid min-h-0 min-w-0 overflow-hidden rounded-[16px] border border-graphite/10 bg-paper [grid-template-rows:48px_minmax(0,1fr)_auto] max-[720px]:min-h-[calc(100dvh-92px)]"
            aria-labelledby="knowledge-chat-title"
          >
            <header className="flex h-12 items-center border-b border-graphite/6 px-4">
              <h1 id="knowledge-chat-title" className="text-base font-semibold">
                Knowledge Chat
              </h1>
            </header>
            <div className="grid min-h-0 place-content-center justify-items-center gap-3 overflow-y-auto bg-mist text-slate">
              <MessagesSquare size={28} />
              <strong className="text-graphite">
                {files.length ? "No indexed files" : "Add a file to start"}
              </strong>
            </div>
            <form
              className="border-t border-graphite/6 p-[0.8rem]"
              onSubmit={(event) => {
                event.preventDefault();
                if (
                  draft.trim() &&
                  files.some((file) => file.status === "indexed")
                )
                  setDraft("");
              }}
            >
              <div className="flex items-center gap-2 rounded-[16px] border border-graphite/16 bg-mist px-3 py-2">
                <textarea
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (
                      event.key === "Enter" &&
                      !event.shiftKey &&
                      !event.nativeEvent.isComposing
                    ) {
                      event.preventDefault();
                      event.currentTarget.form?.requestSubmit();
                    }
                  }}
                  disabled={!files.some((file) => file.status === "indexed")}
                  placeholder="Ask a question"
                  aria-label="Ask this knowledge base"
                  rows={1}
                  className="min-w-0 flex-1 resize-none bg-transparent outline-none"
                />
                <button
                  type="submit"
                  aria-label="Send question"
                  disabled={
                    !draft.trim() ||
                    !files.some((file) => file.status === "indexed")
                  }
                  className="grid size-11 place-items-center rounded-full bg-graphite text-paper disabled:bg-graphite/10 disabled:text-graphite/58"
                >
                  ↑
                </button>
              </div>
            </form>
          </section>
          <section className="knowledge-actions grid min-h-0 min-w-0 overflow-hidden rounded-[16px] border border-graphite/10 bg-paper [grid-template-rows:48px_minmax(0,1fr)] max-[720px]:min-h-[calc(100dvh-92px)]">
            <header className="flex h-12 items-center justify-between border-b border-graphite/10 px-3">
              <h2
                className={
                  toolsCollapsed
                    ? "overflow-hidden opacity-0 max-[720px]:opacity-100"
                    : "font-semibold"
                }
              >
                Tools
              </h2>
              <button
                type="button"
                aria-label={toolsCollapsed ? "Expand tools" : "Collapse tools"}
                aria-expanded={!toolsCollapsed}
                aria-controls="knowledge-actions-body"
                onClick={() => setToolsCollapsed(!toolsCollapsed)}
                className="grid size-10 shrink-0 place-items-center text-slate max-[720px]:hidden"
              >
                {toolsCollapsed ? (
                  <PanelRightOpen size={18} />
                ) : (
                  <PanelRightClose size={18} />
                )}
              </button>
            </header>
            <div
              id="knowledge-actions-body"
              className={`grid min-h-0 [grid-template-rows:repeat(2,minmax(0,1fr))] ${toolsCollapsed ? "invisible opacity-0 max-[720px]:visible max-[720px]:opacity-100" : ""}`}
            >
              <div className="grid min-h-0 content-start gap-2 overflow-y-auto p-4 [grid-template-columns:repeat(auto-fit,minmax(min(100%,104px),1fr))] [grid-auto-rows:74px]">
                {[
                  { label: "Road Map", icon: Map, color: "bg-[#edf4ff]" },
                  { label: "PPT", icon: Presentation, color: "bg-[#fff1e8]" },
                  {
                    label: "Slides",
                    icon: PanelsTopLeft,
                    color: "bg-[#f3efff]",
                  },
                ].map(({ label, icon: Icon, color }) => (
                  <button
                    key={label}
                    type="button"
                    className={`flex h-[74px] flex-col justify-center gap-1 rounded-[16px] px-3 text-left font-medium ${color}`}
                    onClick={() =>
                      void message.info(`${label} is not connected yet.`)
                    }
                  >
                    <Icon size={18} />
                    {label}
                  </button>
                ))}
              </div>
              <div className="border-t border-graphite/10" />
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
