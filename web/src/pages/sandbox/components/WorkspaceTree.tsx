import { useState } from "react";
import { ChevronRight, Folder, FolderOpen } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
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
  toggle: (path: string) => void;
}

function TreeNode({ node, depth, currentPath, onSelect, expanded, toggle }: TreeNodeProps) {
  const hasChildren = Boolean(node.children?.length);
  const isExpanded = expanded.has(node.path);
  const isSelected = currentPath === node.path;

  return (
    <Collapsible open={isExpanded} onOpenChange={() => toggle(node.path)}>
      <CollapsibleTrigger
        render={
          <Button
            type="button"
            variant="ghost"
            className={cn(
              "h-8 w-full justify-start gap-1.5 rounded-md px-2 text-[13px] font-normal transition-none",
              isSelected
                ? "bg-foreground text-background hover:bg-foreground/90 hover:text-background"
                : "text-muted-foreground hover:text-foreground",
            )}
            style={{ paddingLeft: `${8 + depth * 16}px` }}
            aria-current={isSelected ? "page" : undefined}
            onClick={() => onSelect(node.path)}
          />
        }
      >
        <span className="grid size-4 shrink-0 place-items-center">
          <ChevronRight
            className={cn(
              "size-3.5 transition-transform duration-150",
              isExpanded && "rotate-90",
            )}
          />
        </span>
        {isExpanded ? (
          <FolderOpen className="size-4" strokeWidth={1.6} />
        ) : (
          <Folder className="size-4" strokeWidth={1.6} />
        )}
        <span className="truncate">{node.name}</span>
      </CollapsibleTrigger>
      <CollapsibleContent>
        {hasChildren ? (
          <div className="flex flex-col gap-0.5">
            {node.children?.map((child) => (
              <TreeNode
                key={child.path}
                node={child}
                depth={depth + 1}
                currentPath={currentPath}
                onSelect={onSelect}
                expanded={expanded}
                toggle={toggle}
              />
            ))}
          </div>
        ) : null}
      </CollapsibleContent>
    </Collapsible>
  );
}

export default function WorkspaceTree({ nodes, currentPath, onSelect }: WorkspaceTreeProps) {
  const [expanded, setExpanded] = useState(
    () => new Set(["/workspace", "/workspace/outputs"]),
  );

  function toggle(path: string) {
    setExpanded((previous) => {
      const next = new Set(previous);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  return (
    <ScrollArea className="min-h-0 flex-1 px-2 pb-3">
      <nav aria-label="Workspace folders" className="space-y-0.5">
        {nodes.map((node) => (
          <TreeNode
            key={node.path}
            node={node}
            depth={0}
            currentPath={currentPath}
            onSelect={onSelect}
            expanded={expanded}
            toggle={toggle}
          />
        ))}
      </nav>
    </ScrollArea>
  );
}
