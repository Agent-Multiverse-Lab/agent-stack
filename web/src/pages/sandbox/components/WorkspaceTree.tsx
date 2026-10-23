import { ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useTranslation } from "@/i18n";
import { cn } from "@/lib/utils";
import { FolderFillIcon } from "@/pages/sandbox/components/WorkspaceFileList";
import type { WorkspaceTreeNode } from "@/pages/sandbox/types";

interface WorkspaceTreeProps {
  nodes: WorkspaceTreeNode[];
  currentPath: string;
  onSelect: (path: string) => void;
}

export default function WorkspaceTree({
  nodes,
  currentPath,
  onSelect,
}: WorkspaceTreeProps) {
  const { t } = useTranslation();
  const rootNode = nodes[0];
  const primaryFolders = rootNode?.children ?? [];

  // Determine active primary folder (the first segment after /workspace)
  const pathParts = currentPath.split("/").filter(Boolean);
  const activePrimaryPath =
    pathParts.length > 1 ? `/${pathParts.slice(0, 2).join("/")}` : null;

  // Secondary folders under the active primary folder
  const activePrimaryNode = primaryFolders.find(
    (folder) => folder.path === activePrimaryPath,
  );
  const secondaryFolders = activePrimaryNode?.children ?? [];

  return (
    <div className="flex h-full min-h-0 flex-1 divide-x divide-border overflow-hidden">
      {/* Primary Column */}
      <ScrollArea className="h-full w-[170px] shrink-0">
        <nav aria-label={t("Workspace folders")} className="flex flex-col gap-0.5 p-2">
          {/* Workspace Root Button */}
          <Button
            type="button"
            variant="ghost"
            className={cn(
              "h-8 w-full justify-start gap-2 rounded-md px-2 text-[13px] font-medium",
              currentPath === "/workspace" &&
                "bg-selection text-selection-foreground hover:bg-selection",
            )}
            aria-current={currentPath === "/workspace" ? "page" : undefined}
            onClick={() => onSelect("/workspace")}
          >
            <FolderFillIcon className="size-4" />
            <span className="truncate">workspace</span>
          </Button>

          {/* Primary Directories */}
          {primaryFolders.map((folder) => {
            const isSelected =
              currentPath === folder.path || activePrimaryPath === folder.path;
            const hasChildren = (folder.children?.length ?? 0) > 0;
            return (
              <Button
                key={folder.path}
                type="button"
                variant="ghost"
                className={cn(
                  "h-8 w-full justify-between rounded-md px-2 text-[13px] font-medium",
                  isSelected &&
                    "bg-selection text-selection-foreground hover:bg-selection",
                )}
                aria-current={currentPath === folder.path ? "page" : undefined}
                onClick={() => onSelect(folder.path)}
              >
                <span className="flex min-w-0 items-center gap-2">
                  <FolderFillIcon className="size-4" />
                  <span className="truncate">{folder.name}</span>
                </span>
                {hasChildren && (
                  <ChevronRight className="size-3 shrink-0 text-muted-foreground" />
                )}
              </Button>
            );
          })}
        </nav>
      </ScrollArea>

      {/* Secondary Column: only shown when an active primary folder has subfolders or is active */}
      {secondaryFolders.length > 0 && (
        <ScrollArea className="h-full w-[170px] shrink-0 bg-muted/20">
          <nav aria-label={t("Sub-folders")} className="flex flex-col gap-0.5 p-2">
            <div className="px-2 py-1 text-[11px] font-semibold text-muted-foreground uppercase">
              {activePrimaryNode?.name}
            </div>
            {secondaryFolders.map((folder) => {
              const isSelected = currentPath === folder.path;
              return (
                <Button
                  key={folder.path}
                  type="button"
                  variant="ghost"
                  className={cn(
                    "h-8 w-full justify-start gap-2 rounded-md px-2 text-[13px] font-medium",
                    isSelected &&
                      "bg-selection text-selection-foreground hover:bg-selection",
                  )}
                  aria-current={isSelected ? "page" : undefined}
                  onClick={() => onSelect(folder.path)}
                >
                  <FolderFillIcon className="size-4" />
                  <span className="truncate">{folder.name}</span>
                </Button>
              );
            })}
          </nav>
        </ScrollArea>
      )}
    </div>
  );
}
