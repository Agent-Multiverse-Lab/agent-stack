import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  ChevronDown,
  FileText,
  Filter,
  Folder,
  Grid,
  Image as ImageIcon,
  Layers,
  LayoutList,
  Library,
  MoreHorizontal,
  Plus,
  Presentation,
  Search,
  Sparkles,
  StickyNote,
  Table as TableIcon,
  UploadCloud,
  X,
} from "lucide-react";
import { INITIAL_MOCK_ITEMS } from "@/pages/library/mockData";
import CreateDialog from "@/pages/library/components/CreateDialog";
import { useTranslation } from "@/i18n";
import type {
  CreateNotePayload,
  LibraryCategory,
  LibraryItem,
  LibraryItemSource,
  LibraryItemType,
  LibraryViewMode,
} from "@/types/library";

const PAGE_SIZE = 10;
const categories: {
  id: LibraryCategory;
  label: string;
  icon: typeof Layers;
}[] = [
  { id: "all", label: "All", icon: Layers },
  { id: "images", label: "Images", icon: ImageIcon },
  { id: "documents", label: "Documents", icon: FileText },
];
const types: { value: LibraryItemType | "all"; label: string }[] = [
  { value: "all", label: "All Types" },
  { value: "image", label: "Image" },
  { value: "document", label: "Document" },
  { value: "spreadsheet", label: "Spreadsheets" },
  { value: "presentation", label: "Presentation" },
  { value: "folder", label: "Folder" },
  { value: "note", label: "Note" },
];
const sources: { value: LibraryItemSource | "all"; label: string }[] = [
  { value: "all", label: "All Sources" },
  { value: "uploaded", label: "Uploaded" },
  { value: "generated", label: "Generated" },
];
const icons = {
  image: ImageIcon,
  document: FileText,
  spreadsheet: TableIcon,
  presentation: Presentation,
  folder: Folder,
  note: StickyNote,
};
const stamp = () => new Date().toISOString().replace("T", " ").substring(0, 16);
function formatBytes(bytes: number) {
  if (!bytes) return "--";
  const size = ["B", "KB", "MB", "GB"];
  const index = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / 1024 ** index).toFixed(1)} ${size[index]}`;
}

export default function LibraryPage() {
  const { t } = useTranslation();
  const [items, setItems] = useState<LibraryItem[]>([...INITIAL_MOCK_ITEMS]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<LibraryCategory>("all");
  const [fileType, setFileType] = useState<LibraryItemType | "all">("all");
  const [source, setSource] = useState<LibraryItemSource | "all">("all");
  const [viewMode, setViewMode] = useState<LibraryViewMode>("list");
  const [dialog, setDialog] = useState<"folder" | "note" | null>(null);
  const [limit, setLimit] = useState(PAGE_SIZE);
  const [loadingMore, setLoadingMore] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const sentinel = useRef<HTMLDivElement>(null);
  const filtered = useMemo(
    () =>
      items.filter((item) => {
        const q = query.trim().toLowerCase();
        if (
          q &&
          !item.name.toLowerCase().includes(q) &&
          !item.noteContent?.toLowerCase().includes(q)
        )
          return false;
        if (category === "images" && item.type !== "image") return false;
        if (
          category === "documents" &&
          !["document", "spreadsheet", "presentation", "note"].includes(
            item.type,
          )
        )
          return false;
        if (fileType !== "all" && item.type !== fileType) return false;
        if (source !== "all" && item.source !== source) return false;
        return true;
      }),
    [items, query, category, fileType, source],
  );
  const visible = filtered.slice(0, limit);
  const hasMore = limit < filtered.length;
  useEffect(() => {
    const target = sentinel.current;
    if (!target || !hasMore || loadingMore) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setLoadingMore(true);
          window.setTimeout(() => {
            setLimit((previous) => previous + PAGE_SIZE);
            setLoadingMore(false);
          }, 400);
        }
      },
      { rootMargin: "200px", threshold: 0.1 },
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [hasMore, loadingMore, visible.length]);

  function upload(files: FileList) {
    const additions: LibraryItem[] = Array.from(files).map((file, index) => ({
      id: `uploaded-${Date.now()}-${index}`,
      name: file.name,
      type: file.type.startsWith("image/")
        ? "image"
        : /\.(xlsx|csv)$/i.test(file.name)
          ? "spreadsheet"
          : /\.(pptx|ppt)$/i.test(file.name)
            ? "presentation"
            : "document",
      source: "uploaded",
      sizeBytes: file.size,
      mimeType: file.type,
      updatedAt: stamp(),
      createdAt: stamp(),
    }));
    setItems((previous) => [...additions, ...previous]);
    toast.success(t("Successfully uploaded {{files}} file(s)", { files: additions.length }));
  }
  function create(value: string | CreateNotePayload) {
    const now = stamp();
    if (typeof value === "string") {
      setItems((previous) => [
        {
          id: `folder-${Date.now()}`,
          name: value,
          type: "folder",
          source: "uploaded",
          sizeBytes: 0,
          itemCount: 0,
          updatedAt: now,
          createdAt: now,
        },
        ...previous,
      ]);
      toast.success(t("Folder \"{{name}}\" created", { name: value }));
    } else {
      setItems((previous) => [
        {
          id: `note-${Date.now()}`,
          name: value.title,
          type: "note",
          source: "uploaded",
          sizeBytes: new Blob([value.content]).size,
          noteContent: value.content,
          updatedAt: now,
          createdAt: now,
        },
        ...previous,
      ]);
      toast.success(t("Note \"{{name}}\" created", { name: value.title }));
    }
  }
  const actions = (item: LibraryItem) => (
    <DropdownMenu>
      <DropdownMenuTrigger
        type="button"
        aria-label={t("Item actions")}
        title={t("Actions")}
        className="grid size-7 place-items-center rounded-md text-[#64748B] hover:bg-mist"
      >
        <MoreHorizontal size={16} />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem
          onClick={() => toast.info(t("Downloading {{name}}...", { name: item.name }))}
        >
          {t("Download")}
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => toast.success(t("Copied link for {{name}}", { name: item.name }))}
        >
          {t("Copy link")}
        </DropdownMenuItem>
        <DropdownMenuItem
          variant="destructive"
          onClick={() => {
            setItems((previous) =>
              previous.filter((value) => value.id !== item.id),
            );
            toast.info(t("Item deleted"));
          }}
        >
          {t("Delete")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
  return (
    <main
      className="flex h-full min-h-0 w-full justify-center bg-paper text-graphite"
      aria-label={t("Library")}
    >
      <div className="flex h-full min-h-0 w-full max-w-[920px] flex-col bg-paper">
        <header className="flex flex-wrap items-center justify-between gap-4 px-4 py-4">
          <div className="flex items-center gap-2.5">
            <Library size={22} />
            <h1 className="text-xl font-semibold tracking-[-0.02em]">
              {t("Library")}
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex items-center">
              <Search
                className="pointer-events-none absolute left-3 text-[#64748B]"
                size={16}
              />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t("Search...")}
                className="h-9 w-48 rounded-[16px] bg-mist/70 pr-8 pl-9 text-sm outline-none focus:w-60"
              />
              {query && (
                <Button variant="ghost"
                  type="button"
                  aria-label={t("Clear search")}
                  onClick={() => setQuery("")}
                  className="absolute right-2.5"
                >
                  <X size={12} />
                </Button>
              )}
            </div>
            <Input
              ref={fileInput}
              type="file"
              multiple
              className="hidden"
              onChange={(event) => {
                if (event.target.files) upload(event.target.files);
                event.target.value = "";
              }}
            />
            <DropdownMenu>
              <DropdownMenuTrigger
                type="button"
                className="inline-flex h-9 items-center gap-1.5 rounded-[16px] bg-[#0F172A] px-3.5 text-sm font-medium text-paper"
              >
                <Plus size={15} />
                {t("New")}
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => fileInput.current?.click()}>
                  {t("Upload files")}
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setDialog("folder")}>
                  {t("New folder")}
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setDialog("note")}>
                  {t("Quick note")}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2">
          <div className="flex h-8 items-center gap-0.5 rounded-[12px] bg-mist/80 p-0.5">
            {categories.map(({ id, label, icon: Icon }) => (
              <Button variant="ghost"
                key={id}
                type="button"
                onClick={() => setCategory(id)}
                className={`inline-flex h-7 items-center gap-1.5 rounded-[10px] px-3 text-xs ${category === id ? "bg-paper font-medium text-[#0F172A] shadow-sm" : "text-[#64748B]"}`}
              >
                <Icon size={14} />
                {t(label)}
              </Button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger
                type="button"
                className="flex h-8 items-center gap-1.5 rounded-[10px] bg-mist/70 px-2.5 text-xs"
              >
                <Filter size={14} />
                {t(types.find((item) => item.value === fileType)?.label ?? "")}
                <ChevronDown size={14} />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuRadioGroup
                  value={fileType}
                  onValueChange={(value) =>
                    setFileType(value as LibraryItemType | "all")
                  }
                >
                  {types.map((item) => (
                    <DropdownMenuRadioItem
                      key={item.value}
                      value={item.value}
                    >
                      {t(item.label)}
                    </DropdownMenuRadioItem>
                  ))}
                </DropdownMenuRadioGroup>
              </DropdownMenuContent>
            </DropdownMenu>
            <DropdownMenu>
              <DropdownMenuTrigger
                type="button"
                className="flex h-8 items-center gap-1.5 rounded-[10px] bg-mist/70 px-2.5 text-xs"
              >
                {t(sources.find((item) => item.value === source)?.label ?? "")}
                <ChevronDown size={14} />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuRadioGroup
                  value={source}
                  onValueChange={(value) =>
                    setSource(value as LibraryItemSource | "all")
                  }
                >
                  {sources.map((item) => (
                    <DropdownMenuRadioItem
                      key={item.value}
                      value={item.value}
                    >
                      {t(item.label)}
                    </DropdownMenuRadioItem>
                  ))}
                </DropdownMenuRadioGroup>
              </DropdownMenuContent>
            </DropdownMenu>
            <div className="flex h-8 rounded-[12px] bg-mist/80 p-0.5">
              <Button variant="ghost"
                type="button"
                aria-label={t("List view")}
                onClick={() => setViewMode("list")}
                className={`grid size-7 place-items-center rounded-[10px] ${viewMode === "list" ? "bg-paper" : ""}`}
              >
                <LayoutList size={14} />
              </Button>
              <Button variant="ghost"
                type="button"
                aria-label={t("Grid view")}
                onClick={() => setViewMode("grid")}
                className={`grid size-7 place-items-center rounded-[10px] ${viewMode === "grid" ? "bg-paper" : ""}`}
              >
                <Grid size={14} />
              </Button>
            </div>
          </div>
        </div>
        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-4 py-4">
          {!visible.length ? (
            <div className="my-auto grid justify-items-center py-16 text-center">
              <Folder size={24} className="mb-3 text-slate" />
              <h3 className="text-sm font-medium">{t("No items found")}</h3>
              <p className="mt-1 text-xs text-slate">
                {t("No files, notes, or folders match your search or filter criteria.")}
              </p>
            </div>
          ) : viewMode === "list" ? (
            <Table className="w-full border-collapse text-left text-xs">
              <TableHeader>
                <TableRow className="border-0 text-[#94A3B8] hover:bg-transparent">
                  <TableHead className="h-auto px-2 pb-3 text-left font-medium">{t("NAME")}</TableHead>
                  <TableHead className="h-auto px-4 pb-3 text-left font-medium">{t("MODIFIED")}</TableHead>
                  <TableHead className="h-auto px-4 pb-3 text-left font-medium">{t("SIZE")}</TableHead>
                  <TableHead className="h-auto" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {visible.map((item) => {
                  const Icon = icons[item.type];
                  return (
                    <TableRow key={item.id} className="group h-[46px] border-0 hover:bg-transparent">
                      <TableCell className="py-3 pr-4 pl-2">
                        <div className="flex items-center gap-3">
                          <Icon size={18} className="shrink-0 text-[#64748B]" />
                          <span
                            className="truncate text-sm font-medium text-[#0F172A]"
                            title={item.name}
                          >
                            {item.name}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="px-4 py-3 text-[13px] text-[#64748B]">
                        {item.createdAt || item.updatedAt}
                      </TableCell>
                      <TableCell className="px-4 py-3 font-mono text-[13px] text-[#64748B]">
                        {formatBytes(item.sizeBytes)}
                      </TableCell>
                      <TableCell className="px-2 py-3 text-right">
                        <div className="flex justify-end opacity-0 group-hover:opacity-100 group-focus-within:opacity-100">
                          {actions(item)}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          ) : (
            <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-5 py-2">
              {visible.map((item) => {
                const Icon = icons[item.type];
                return (
                  <div
                    key={item.id}
                    className="group relative flex flex-col justify-between p-2"
                  >
                    <div className="relative mb-2.5 flex h-26 items-center justify-center overflow-hidden rounded-xl bg-mist/50">
                      {item.type === "image" && item.thumbnailUrl ? (
                        <img
                          src={item.thumbnailUrl}
                          alt={item.name}
                          className="size-full object-cover"
                        />
                      ) : (
                        <Icon size={32} className="text-[#64748B]" />
                      )}
                      <div className="absolute top-2 left-2 flex items-center gap-1 text-[10px] text-slate">
                        {item.source === "generated" ? (
                          <Sparkles size={9} />
                        ) : (
                          <UploadCloud size={9} />
                        )}
                        {t(item.source)}
                      </div>
                      <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100">
                        {actions(item)}
                      </div>
                    </div>
                    <h4
                      className="truncate text-sm font-medium"
                      title={item.name}
                    >
                      {item.name}
                    </h4>
                    <div className="mt-1.5 flex justify-between text-[13px] text-[#64748B]">
                      <span>{item.createdAt || item.updatedAt}</span>
                      <span>{formatBytes(item.sizeBytes)}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          <div
            ref={sentinel}
            className="mt-6 flex justify-center py-4 text-xs text-[#64748B]"
          >
            {loadingMore
              ? t("Loading more items...")
              : !hasMore && visible.length > 0
                ? t("All items loaded (Max 10 per page)")
                : ""}
          </div>
        </div>
      </div>
      {dialog && (
        <CreateDialog
          key={dialog}
          kind={dialog}
          close={() => setDialog(null)}
          create={create}
        />
      )}
    </main>
  );
}
