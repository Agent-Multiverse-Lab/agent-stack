export interface WorkspaceEntry {
  name: string;
  path: string;
  kind: "directory" | "file";
  size: number | null;
  modifiedAt: string;
  fileType?: "code" | "data" | "document" | "image";
}

export interface WorkspaceTreeNode {
  name: string;
  path: string;
  children?: WorkspaceTreeNode[];
}
