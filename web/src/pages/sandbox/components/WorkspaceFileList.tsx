import {
  Braces,
  FileCode2,
  FileImage,
  FilePenLine,
  FileText,
  Folder,
  MoreHorizontal,
  Pencil,
  Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Item, ItemActions, ItemGroup, ItemMedia, ItemTitle } from "@/components/ui/item";
import { useTranslation } from "@/i18n";
import { cn } from "@/lib/utils";
import type { WorkspaceEntry, WorkspaceFileAction } from "@/pages/sandbox/types";

export function FolderFillIcon({ className }: { className?: string }) {
  return (
    <Folder
      className={cn(
        "size-5 shrink-0 fill-amber-400 stroke-amber-600 text-amber-600 dark:fill-amber-500 dark:stroke-amber-400",
        className,
      )}
    />
  );
}

interface WorkspaceFileListProps {
  entries: WorkspaceEntry[];
  selectedPath: string | null;
  query: string;
  onSelect: (entry: WorkspaceEntry) => void;
  onOpenFolder: (path: string) => void;
  onAction: (entry: WorkspaceEntry, action: WorkspaceFileAction) => void;
}

export default function WorkspaceFileList({
  entries,
  selectedPath,
  query,
  onSelect,
  onOpenFolder,
  onAction,
}: WorkspaceFileListProps) {
  const { t } = useTranslation();
  const normalized = query.trim().toLocaleLowerCase();
  const visibleEntries = entries
    .filter((entry) => entry.name.toLocaleLowerCase().includes(normalized))
    .sort((left, right) => {
      if (left.kind !== right.kind) return left.kind === "directory" ? -1 : 1;
      return left.name.localeCompare(right.name, undefined, { numeric: true });
    });

  return (
    <ItemGroup aria-label={t("Workspace files")} className="gap-1 p-3">
      {visibleEntries.length ? (
        visibleEntries.map((entry) => {
          const selected = entry.path === selectedPath;
          const isDir = entry.kind === "directory";
          return (
            <div key={entry.path} role="listitem">
              <Item
                className={cn(
                  "h-12 flex-nowrap gap-0 rounded-md border-0 p-0 hover:bg-muted",
                  selected &&
                    "bg-selection text-selection-foreground hover:bg-selection",
                )}
              >
                <Button
                  type="button"
                  variant="ghost"
                  className="h-full min-w-0 flex-1 justify-start gap-2.5 rounded-md px-3 text-left font-normal hover:bg-transparent aria-[current=true]:text-selection-foreground aria-[current=true]:hover:text-selection-foreground"
                  aria-current={selected ? "true" : undefined}
                  onClick={() =>
                    isDir ? onOpenFolder(entry.path) : onSelect(entry)
                  }
                >
                  <ItemMedia className="text-muted-foreground">
                    {isDir ? (
                      <FolderFillIcon />
                    ) : entry.fileType === "image" ? (
                      <FileImage className="size-5 text-sky-600 dark:text-sky-400" strokeWidth={1.5} />
                    ) : entry.fileType === "code" ? (
                      <FileCode2 className="size-5 text-emerald-600 dark:text-emerald-400" strokeWidth={1.5} />
                    ) : entry.fileType === "data" ? (
                      <Braces className="size-5 text-orange-600 dark:text-orange-400" strokeWidth={1.5} />
                    ) : (
                      <FileText className="size-5 text-muted-foreground" strokeWidth={1.5} />
                    )}
                  </ItemMedia>
                  <ItemTitle className="block truncate font-normal">
                    {entry.name}
                  </ItemTitle>
                </Button>
                {entry.kind === "file" && (
                  <ItemActions className="pr-3">
                    <DropdownMenu>
                      <DropdownMenuTrigger
                        render={
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-sm"
                            className="rounded-md"
                          />
                        }
                        aria-label={t("File actions: {{name}}", {
                          name: entry.name,
                        })}
                      >
                        <MoreHorizontal />
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-36">
                        <DropdownMenuItem
                          onClick={() => onAction(entry, "rename")}
                        >
                          <Pencil />
                          {t("Rename")}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => onAction(entry, "edit")}
                        >
                          <FilePenLine />
                          {t("Edit content")}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          variant="destructive"
                          onClick={() => onAction(entry, "delete")}
                        >
                          <Trash2 />
                          {t("Delete")}
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </ItemActions>
                )}
              </Item>
            </div>
          );
        })
      ) : (
        <p className="px-4 py-12 text-center text-sm text-muted-foreground">
          {t(normalized ? "No matching files" : "This folder is empty")}
        </p>
      )}
    </ItemGroup>
  );
}
