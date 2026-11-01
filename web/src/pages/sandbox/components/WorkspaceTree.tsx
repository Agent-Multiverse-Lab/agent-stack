import { useRef } from "react";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Spinner } from "@/components/ui/spinner";
import { useTranslation } from "@/i18n";
import { cn } from "@/lib/utils";
import { FolderFillIcon } from "@/pages/sandbox/components/WorkspaceFileList";
import type { WorkspaceTreeNode } from "@/pages/sandbox/types";

interface WorkspaceTreeProps {
  nodes: WorkspaceTreeNode[];
  currentPath: string;
  onSelect: (path: string) => void;
  onUpload?: (files: File[]) => void;
  isUploading?: boolean;
  uploadError?: string;
}

export default function WorkspaceTree({
  nodes,
  currentPath,
  onSelect,
  onUpload,
  isUploading = false,
  uploadError,
}: WorkspaceTreeProps) {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const rootNode = nodes[0];
  const primaryFolders = (rootNode?.children ?? []).filter(
    (folder) => folder.name !== "outputs" && folder.path !== "/workspace/outputs",
  );

  return (
    <div className="flex h-full min-h-0 w-[180px] shrink-0 flex-col overflow-hidden bg-card">
      {onUpload && (
        <div className="p-2 border-b border-border">
          <Input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            aria-label={t("Add document")}
            onChange={(event) => {
              const files = Array.from(event.target.files ?? []);
              if (files.length > 0) {
                onUpload(files);
              }
              event.target.value = "";
            }}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 w-full justify-center gap-1.5 text-xs font-medium"
            disabled={isUploading}
            onClick={() => fileInputRef.current?.click()}
          >
            {isUploading ? (
              <Spinner className="size-3.5" />
            ) : (
              <Upload className="size-3.5" />
            )}
            <span>{t("Add document")}</span>
          </Button>
          {uploadError && (
            <p
              role="alert"
              className="mt-1 px-1 text-xs text-destructive truncate"
              title={uploadError}
            >
              {uploadError}
            </p>
          )}
        </div>
      )}

      <ScrollArea className="h-full min-h-0 flex-1">
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

          {/* Primary Directories without recursion */}
          {primaryFolders.map((folder) => {
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
    </div>
  );
}
