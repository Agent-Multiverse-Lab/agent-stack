import { useEffect, useState } from "react";
import { ChevronRight, Folder, FolderOpen } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useTranslation } from "@/i18n";
import { cn } from "@/lib/utils";
import type { WorkspaceTreeNode } from "@/pages/sandbox/types";

interface WorkspaceTreeProps {
  nodes: WorkspaceTreeNode[];
  currentPath: string;
  onSelect: (path: string) => void;
}

interface TreeNodeProps extends Omit<WorkspaceTreeProps, "nodes"> {
  node: WorkspaceTreeNode;
  depth: number;
  expanded: Set<string>;
  toggle: (path: string, open: boolean) => void;
}

function TreeNode({ node, depth, currentPath, onSelect, expanded, toggle }: TreeNodeProps) {
  const { t } = useTranslation();
  const open = expanded.has(node.path);
  const selected = currentPath === node.path;
  const Icon = open ? FolderOpen : Folder;
  return (
    <Collapsible open={open} onOpenChange={(next) => {
      toggle(node.path, next);
      if (next) onSelect(node.path);
    }}>
      <div className={cn("flex h-9 items-center pr-2", selected && "bg-selection shadow-[inset_3px_0_0_var(--selection-foreground)]")}
        style={{ paddingLeft: 8 + depth * 14 }}>
        <CollapsibleTrigger render={
          <Button type="button" variant="ghost" size="icon-xs" className="shrink-0 rounded-none"
            aria-label={t(open ? "Collapse {{name}}" : "Expand {{name}}", { name: node.name })} />
        }>
          <ChevronRight className={cn("size-3 transition-transform motion-reduce:transition-none", open && "rotate-90")} />
        </CollapsibleTrigger>
        <Button type="button" variant="ghost"
          className={cn("h-9 min-w-0 flex-1 justify-start gap-2 rounded-none px-1.5 text-[13px] font-normal", selected && "font-medium text-selection-foreground hover:bg-selection hover:text-selection-foreground")}
          aria-current={selected ? "page" : undefined}
          onClick={() => { toggle(node.path, true); onSelect(node.path); }}>
          <Icon className="size-4 shrink-0" strokeWidth={1.5} />
          <span className="truncate">{node.name}</span>
        </Button>
      </div>
      <CollapsibleContent>
        {node.children?.map((child) => (
          <TreeNode key={child.path} node={child} depth={depth + 1} currentPath={currentPath}
            onSelect={onSelect} expanded={expanded} toggle={toggle} />
        ))}
      </CollapsibleContent>
    </Collapsible>
  );
}

export default function WorkspaceTree({ nodes, currentPath, onSelect }: WorkspaceTreeProps) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(() => new Set(["/workspace"]));
  useEffect(() => {
    const parts = currentPath.split("/").filter(Boolean);
    setExpanded((previous) => {
      const next = new Set(previous);
      parts.forEach((_, index) => next.add(`/${parts.slice(0, index + 1).join("/")}`));
      return next;
    });
  }, [currentPath]);

  function toggle(path: string, open: boolean) {
    setExpanded((previous) => {
      const next = new Set(previous);
      if (open) next.add(path); else next.delete(path);
      return next;
    });
  }

  return (
    <ScrollArea className="min-h-0 flex-1 pb-3">
      <nav aria-label={t("Workspace folders")}>
        {nodes.map((node) => (
          <TreeNode key={node.path} node={node} depth={0} currentPath={currentPath}
            onSelect={onSelect} expanded={expanded} toggle={toggle} />
        ))}
      </nav>
    </ScrollArea>
  );
}
