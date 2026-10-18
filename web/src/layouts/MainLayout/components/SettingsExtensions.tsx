import { useRef, useState } from "react";
import { Blocks, Info, Plug, Plus, RotateCcw, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Empty, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { useTranslation } from "@/i18n";
import { ExtensionDialog } from "./settings-extensions/ExtensionDialog";
import { SkillCard } from "./settings-extensions/SkillCard";
import { McpCard } from "./settings-extensions/McpCard";
import { createPreviewItem, createPreviewItems, type ExtensionKind, type ExtensionPreview } from "./settings-extensions/extension-preview-data";

type Filter = "all" | "enabled" | "disabled";
interface Selection { item: ExtensionPreview; isNew: boolean; session: number }

/** Each section starts from the real, server-managed state. Sample data requires opt-in. */
export function SettingsExtensions({ kind }: { kind: ExtensionKind }) {
  return <ExtensionSettings key={kind} kind={kind} />;
}

function ExtensionSettings({ kind }: { kind: ExtensionKind }) {
  const { t } = useTranslation();
  const [isPreview, setIsPreview] = useState(false);
  const [items, setItems] = useState<ExtensionPreview[]>([]);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [selection, setSelection] = useState<Selection | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const previewButtonRef = useRef<HTMLButtonElement>(null);
  const sessionRef = useRef(0);
  const nextIdRef = useRef(0);
  const Icon = kind === "skills" ? Blocks : Plug;

  function resetPreview() {
    setItems(createPreviewItems(kind, t));
    setSearch("");
    setFilter("all");
    setSelection(null);
    setIsDialogOpen(false);
    nextIdRef.current = 0;
  }

  function openItem(item: ExtensionPreview, target: HTMLButtonElement, isNew = false) {
    returnFocusRef.current = target;
    setSelection({ item, isNew, session: ++sessionRef.current });
    setIsDialogOpen(true);
  }

  if (!isPreview) {
    return (
      <Empty className="min-h-[390px] justify-center border-0">
        <EmptyHeader>
          <EmptyMedia variant="icon"><Icon aria-hidden="true" /></EmptyMedia>
          <EmptyTitle>{t("Management unavailable")}</EmptyTitle>
        </EmptyHeader>
        <Button ref={previewButtonRef} variant="outline" onClick={() => {
          resetPreview();
          setAnnouncement("");
          setIsPreview(true);
        }}>{t("Explore local preview")}</Button>
      </Empty>
    );
  }

  const query = search.trim().toLocaleLowerCase();
  const visibleItems = items.filter((item) => {
    const matchesSearch = [item.name, item.id, item.description].some((value) => value.toLocaleLowerCase().includes(query));
    return matchesSearch && (filter === "all" || item.isEnabled === (filter === "enabled"));
  });

  return (
    <div className="flex min-h-[390px] min-w-0 flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Info aria-hidden="true" className="size-4 shrink-0" />
          <span>{t("Local preview · No server changes")}</span>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => { resetPreview(); setAnnouncement(t("Preview reset to the original examples")); }}>
            <RotateCcw aria-hidden="true" />{t("Reset preview")}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => {
            setItems([]); setSearch(""); setFilter("all"); setSelection(null); setIsDialogOpen(false); setIsPreview(false);
            setAnnouncement("");
            requestAnimationFrame(() => previewButtonRef.current?.focus());
          }}>{t("Exit preview")}</Button>
        </div>
      </div>

      <div className="flex items-center justify-between gap-4">
        <InputGroup className="max-w-[280px]">
          <InputGroupAddon><Search aria-hidden="true" /></InputGroupAddon>
          <InputGroupInput ref={searchInputRef} value={search} onChange={(event) => setSearch(event.target.value)}
            aria-label={t(kind === "skills" ? "Search example skills" : "Search example MCP services")}
            placeholder={t(kind === "skills" ? "Search skills" : "Search MCP services")} />
        </InputGroup>
        <Button aria-haspopup="dialog" onClick={(event) => openItem(createPreviewItem(kind, `local-example-${++nextIdRef.current}`), event.currentTarget, true)}>
          <Plus aria-hidden="true" />{t(kind === "skills" ? "Add example skill" : "Add example MCP service")}
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2" role="group" aria-label={t("Filter examples")}>
        {(["all", "enabled", "disabled"] as const).map((value) => (
          <Button key={value} size="sm" variant={filter === value ? "secondary" : "ghost"}
            aria-pressed={filter === value} onClick={() => setFilter(value)}>
            {t(value === "all" ? "All" : value === "enabled" ? "Enabled" : "Disabled")}{" "}
            <Badge>{items.filter((item) => value === "all" || item.isEnabled === (value === "enabled")).length}</Badge>
          </Button>
        ))}
      </div>

      <div className="min-w-0">
        <div className="grid grid-cols-[minmax(0,1fr)_144px_120px_16px] gap-4 border-b px-3 pb-3 text-xs text-muted-foreground" aria-hidden="true">
          <span>{t(kind === "skills" ? "Skill name" : "Service name")}</span>
          <span>{t(kind === "skills" ? "Scope" : "Transport")}</span>
          <span>{t("Preview status")}</span>
        </div>
        {visibleItems.length ? (
          <ul className="m-0 list-none divide-y p-0" aria-label={t(kind === "skills" ? "Example skills" : "Example MCP services")}>
            {visibleItems.map((item) => <li key={item.id}>
              {item.kind === "skills"
                ? <SkillCard item={item} onOpen={(target) => openItem(item, target)} />
                : <McpCard item={item} onOpen={(target) => openItem(item, target)} />}
            </li>)}
          </ul>
        ) : (
          <Empty className="min-h-48 border-0">
            <EmptyHeader><EmptyMedia variant="icon"><Search aria-hidden="true" /></EmptyMedia>
              <EmptyTitle>{t("No matching examples")}</EmptyTitle>
            </EmptyHeader>
            <Button variant="outline" size="sm" onClick={() => { setSearch(""); setFilter("all"); }}>{t("Clear filters")}</Button>
          </Empty>
        )}
      </div>
      <p className="sr-only" role="status">{announcement}</p>

      {selection && <ExtensionDialog key={selection.session} item={selection.item} isNew={selection.isNew}
        isOpen={isDialogOpen} returnFocusRef={returnFocusRef} fallbackFocusRef={searchInputRef}
        onApply={(updated) => {
          setItems((previous) => previous.some((item) => item.id === updated.id)
            ? previous.map((item) => item.id === updated.id ? updated : item) : [...previous, updated]);
          setAnnouncement(t("Applied to this preview only"));
        }}
        onClose={() => setIsDialogOpen(false)}
        onClosed={() => setSelection((current) => current?.session === selection.session ? null : current)} />}
    </div>
  );
}
