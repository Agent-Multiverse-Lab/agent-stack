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

export interface SandboxWorkspaceResponse {
  thread_id: string;
  sandbox_id: string;
  status: string;
  path: string;
  entries: Array<{
    name: string;
    path: string;
    kind: "directory" | "file";
    size: number | null;
    modified_at: string;
    file_type?: "code" | "data" | "document" | "image" | null;
  }>;
}
