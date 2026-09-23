import { useEffect, useMemo, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Braces,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  FileCode2,
  FileImage,
  FileText,
  Folder,
  Search,
  SlidersHorizontal,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useTranslation } from "@/i18n";
import { cn } from "@/lib/utils";
import type { WorkspaceEntry } from "@/pages/sandbox/types";

type SortKey = "name" | "modifiedAt" | "size";
type SortDirection = "asc" | "desc";
type OptionalColumn = "modifiedAt" | "size";

interface WorkspaceFileListProps {
  entries: WorkspaceEntry[];
  selectedPath: string | null;
  query: string;
  emptyMessage: string;
  onQueryChange: (query: string) => void;
  onSelect: (entry: WorkspaceEntry) => void;
  onOpenFolder: (path: string) => void;
}

function formatBytes(bytes: number | null) {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function EntryIcon({ entry }: { entry: WorkspaceEntry }) {
  if (entry.kind === "directory") return <Folder className="size-[18px] text-amber-600 dark:text-amber-400" />;
  if (entry.fileType === "image") return <FileImage className="size-[18px] text-sky-600 dark:text-sky-400" />;
  if (entry.fileType === "code") return <FileCode2 className="size-[18px] text-emerald-600 dark:text-emerald-400" />;
  if (entry.fileType === "data") return <Braces className="size-[18px] text-orange-600 dark:text-orange-400" />;
  return <FileText className="size-[18px] text-muted-foreground" />;
}

function SortableHeader({
  active,
  direction,
  label,
  onClick,
  className,
}: {
  active: boolean;
  direction: SortDirection;
  label: string;
  onClick: () => void;
  className?: string;
}) {
  const Icon = active ? (direction === "asc" ? ArrowUp : ArrowDown) : ArrowUpDown;
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className={cn("-ml-3 h-8 gap-1.5 px-3 text-xs font-medium", className)}
      onClick={onClick}
    >
      {label}
      <Icon className={cn("size-3.5", !active && "text-muted-foreground/60")} />
    </Button>
  );
}

export default function WorkspaceFileList({
  entries,
  selectedPath,
  query,
  emptyMessage,
  onQueryChange,
  onSelect,
  onOpenFolder,
}: WorkspaceFileListProps) {
  const { t } = useTranslation();
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(() => new Set());
  const [visibleColumns, setVisibleColumns] = useState<Record<OptionalColumn, boolean>>({
    modifiedAt: true,
    size: true,
  });
  const [pageSize, setPageSize] = useState(10);
  const [pageIndex, setPageIndex] = useState(0);

  const sortedEntries = useMemo(() => {
    const values = [...entries];
    values.sort((left, right) => {
      if (left.kind !== right.kind) return left.kind === "directory" ? -1 : 1;
      let result = 0;
      if (sortKey === "name") result = left.name.localeCompare(right.name, undefined, { numeric: true });
      if (sortKey === "modifiedAt") result = left.modifiedAt.localeCompare(right.modifiedAt);
      if (sortKey === "size") result = (left.size ?? -1) - (right.size ?? -1);
      return sortDirection === "asc" ? result : -result;
    });
    return values;
  }, [entries, sortDirection, sortKey]);

  const pageCount = Math.max(1, Math.ceil(sortedEntries.length / pageSize));
  const currentPage = Math.min(pageIndex, pageCount - 1);
  const pageEntries = sortedEntries.slice(currentPage * pageSize, (currentPage + 1) * pageSize);
  const allPageSelected = pageEntries.length > 0 && pageEntries.every((entry) => selectedPaths.has(entry.path));

  useEffect(() => {
    setPageIndex(0);
  }, [entries, pageSize]);

  useEffect(() => {
    const availablePaths = new Set(entries.map((entry) => entry.path));
    setSelectedPaths((previous) => new Set([...previous].filter((path) => availablePaths.has(path))));
  }, [entries]);

  function toggleSort(nextKey: SortKey) {
    if (nextKey === sortKey) setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
    else {
      setSortKey(nextKey);
      setSortDirection("asc");
    }
    setPageIndex(0);
  }

  function togglePath(path: string, checked: boolean) {
    setSelectedPaths((previous) => {
      const next = new Set(previous);
      if (checked) next.add(path);
      else next.delete(path);
      return next;
    });
  }

  function togglePage(checked: boolean) {
    setSelectedPaths((previous) => {
      const next = new Set(previous);
      pageEntries.forEach((entry) => {
        if (checked) next.add(entry.path);
        else next.delete(entry.path);
      });
      return next;
    });
  }

  const visibleColumnCount = 2 + Number(visibleColumns.modifiedAt) + Number(visibleColumns.size);

  return (
    <section className="flex min-h-full flex-col gap-3 p-3 sm:p-4" aria-label={t("Workspace files")}>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-sm">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder={t("Filter this folder")}
            aria-label={t("Filter this folder")}
            className="h-9 bg-background pl-8"
          />
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button type="button" variant="outline" size="sm" className="w-full justify-between sm:w-auto" />
            }
          >
            <span className="flex items-center gap-2">
              <SlidersHorizontal className="size-3.5" />
              {t("Columns")}
            </span>
            <ChevronDown className="size-3.5 text-muted-foreground" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="min-w-40">
            <DropdownMenuCheckboxItem
              checked={visibleColumns.modifiedAt}
              onCheckedChange={(checked) => setVisibleColumns((current) => ({ ...current, modifiedAt: checked }))}
            >
              {t("MODIFIED")}
            </DropdownMenuCheckboxItem>
            <DropdownMenuCheckboxItem
              checked={visibleColumns.size}
              onCheckedChange={(checked) => setVisibleColumns((current) => ({ ...current, size: checked }))}
            >
              {t("SIZE")}
            </DropdownMenuCheckboxItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="overflow-hidden rounded-lg border border-border/80 bg-card">
        <Table>
          <TableHeader className="bg-muted/35">
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-11 pl-4">
                <Checkbox
                  checked={allPageSelected}
                  onCheckedChange={(checked) => togglePage(checked)}
                  aria-label={t("Select all rows")}
                />
              </TableHead>
              <TableHead
                className="min-w-52"
                aria-sort={sortKey === "name" ? (sortDirection === "asc" ? "ascending" : "descending") : "none"}
              >
                <SortableHeader
                  active={sortKey === "name"}
                  direction={sortDirection}
                  label={t("NAME")}
                  onClick={() => toggleSort("name")}
                />
              </TableHead>
              {visibleColumns.modifiedAt ? (
                <TableHead
                  className="hidden w-52 md:table-cell"
                  aria-sort={sortKey === "modifiedAt" ? (sortDirection === "asc" ? "ascending" : "descending") : "none"}
                >
                  <SortableHeader
                    active={sortKey === "modifiedAt"}
                    direction={sortDirection}
                    label={t("MODIFIED")}
                    onClick={() => toggleSort("modifiedAt")}
                  />
                </TableHead>
              ) : null}
              {visibleColumns.size ? (
                <TableHead
                  className="w-28 pr-4 text-right"
                  aria-sort={sortKey === "size" ? (sortDirection === "asc" ? "ascending" : "descending") : "none"}
                >
                  <SortableHeader
                    active={sortKey === "size"}
                    direction={sortDirection}
                    label={t("SIZE")}
                    onClick={() => toggleSort("size")}
                    className="ml-auto"
                  />
                </TableHead>
              ) : null}
            </TableRow>
          </TableHeader>
          <TableBody>
            {pageEntries.length ? pageEntries.map((entry) => {
              const rowSelected = selectedPath === entry.path;
              const checked = selectedPaths.has(entry.path);
              return (
                <TableRow
                  key={entry.path}
                  data-state={checked ? "selected" : undefined}
                  className={cn(
                    "h-13 cursor-default border-border/60",
                    checked && "bg-muted/60",
                    rowSelected && !checked && "bg-muted/40",
                  )}
                  onClick={() => onSelect(entry)}
                  onDoubleClick={() => entry.kind === "directory" && onOpenFolder(entry.path)}
                >
                  <TableCell className="pl-4" onClick={(event) => event.stopPropagation()}>
                    <Checkbox
                      checked={checked}
                      onCheckedChange={(nextChecked) => togglePath(entry.path, nextChecked)}
                      aria-label={t("Select {{name}}", { name: entry.name })}
                    />
                  </TableCell>
                  <TableCell className="min-w-0 py-2">
                    <Button
                      type="button"
                      variant="ghost"
                      className="h-9 min-w-0 max-w-full justify-start gap-2.5 px-1.5 font-normal hover:bg-transparent"
                      onClick={() => {
                        onSelect(entry);
                        if (entry.kind === "directory") onOpenFolder(entry.path);
                      }}
                    >
                      <EntryIcon entry={entry} />
                      <span className="truncate text-sm font-medium">{entry.name}</span>
                    </Button>
                  </TableCell>
                  {visibleColumns.modifiedAt ? (
                    <TableCell className="hidden text-xs tabular-nums text-muted-foreground md:table-cell">
                      {formatDate(entry.modifiedAt)}
                    </TableCell>
                  ) : null}
                  {visibleColumns.size ? (
                    <TableCell className="pr-4 text-right font-mono text-xs tabular-nums text-muted-foreground">
                      {formatBytes(entry.size)}
                    </TableCell>
                  ) : null}
                </TableRow>
              );
            }) : (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={visibleColumnCount} className="h-56 text-center">
                  <Folder className="mx-auto mb-3 size-7 text-muted-foreground/60" />
                  <p className="text-sm text-muted-foreground">{emptyMessage}</p>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex flex-col gap-3 px-1 text-xs text-muted-foreground sm:flex-row sm:items-center">
        <p className="flex-1">
          {t("{{selected}} of {{total}} row(s) selected", {
            selected: selectedPaths.size,
            total: sortedEntries.length,
          })}
        </p>
        <div className="flex items-center justify-between gap-3 sm:justify-end">
          <div className="hidden items-center gap-2 md:flex">
            <span>{t("Rows per page")}</span>
            <Select value={String(pageSize)} onValueChange={(value) => setPageSize(Number(value))}>
              <SelectTrigger className="h-8 w-18">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[10, 20, 50].map((size) => <SelectItem key={size} value={String(size)}>{size}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <span className="min-w-20 text-center font-medium text-foreground">
            {t("Page {{page}} of {{count}}", { page: currentPage + 1, count: pageCount })}
          </span>
          <div className="flex items-center gap-1">
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              disabled={currentPage === 0}
              onClick={() => setPageIndex((current) => Math.max(0, current - 1))}
              aria-label={t("Previous page")}
            >
              <ChevronLeft />
            </Button>
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              disabled={currentPage >= pageCount - 1}
              onClick={() => setPageIndex((current) => Math.min(pageCount - 1, current + 1))}
              aria-label={t("Next page")}
            >
              <ChevronRight />
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}
