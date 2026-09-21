import { Braces, FileCode2, FileImage, FileText, Folder } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { WorkspaceEntry } from "@/pages/sandbox/types";

interface WorkspaceFileListProps {
  entries: WorkspaceEntry[];
  selectedPath: string | null;
  onSelect: (entry: WorkspaceEntry) => void;
  onOpenFolder: (path: string) => void;
  labels: { name: string; modified: string; size: string; empty: string };
}

function formatBytes(bytes: number | null) {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

function EntryIcon({ entry }: { entry: WorkspaceEntry }) {
  if (entry.kind === "directory") return <Folder className="size-[18px] text-amber-600 dark:text-amber-400" />;
  if (entry.fileType === "image") return <FileImage className="size-[18px] text-sky-600 dark:text-sky-400" />;
  if (entry.fileType === "code") return <FileCode2 className="size-[18px] text-emerald-600 dark:text-emerald-400" />;
  if (entry.fileType === "data") return <Braces className="size-[18px] text-orange-600 dark:text-orange-400" />;
  return <FileText className="size-[18px] text-muted-foreground" />;
}

export default function WorkspaceFileList({ entries, selectedPath, onSelect, onOpenFolder, labels }: WorkspaceFileListProps) {
  if (!entries.length) {
    return (
      <div className="grid min-h-56 place-items-center px-6 text-center">
        <div>
          <Folder className="mx-auto mb-3 size-7 text-muted-foreground/60" />
          <p className="text-sm text-muted-foreground">{labels.empty}</p>
        </div>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow className="border-border/60 hover:bg-transparent">
          <TableHead className="h-9 pl-4 text-[11px] font-medium tracking-[0.08em] text-muted-foreground">{labels.name}</TableHead>
          <TableHead className="hidden h-9 w-44 text-[11px] font-medium tracking-[0.08em] text-muted-foreground sm:table-cell">{labels.modified}</TableHead>
          <TableHead className="h-9 w-24 pr-4 text-right text-[11px] font-medium tracking-[0.08em] text-muted-foreground">{labels.size}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {entries.map((entry) => {
          const selected = selectedPath === entry.path;
          return (
            <TableRow
              key={entry.path}
              data-state={selected ? "selected" : undefined}
              className={cn("h-12 cursor-default border-border/45 transition-colors", selected && "bg-muted/70")}
              onClick={() => onSelect(entry)}
              onDoubleClick={() => entry.kind === "directory" && onOpenFolder(entry.path)}
            >
              <TableCell className="py-1.5 pr-3 pl-3">
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
                  <span className="truncate text-[13px] font-medium">{entry.name}</span>
                </Button>
              </TableCell>
              <TableCell className="hidden text-xs text-muted-foreground sm:table-cell">{entry.modifiedAt}</TableCell>
              <TableCell className="pr-4 text-right font-mono text-[11px] text-muted-foreground">{formatBytes(entry.size)}</TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
