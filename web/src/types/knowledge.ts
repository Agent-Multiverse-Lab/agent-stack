export type KnowledgeFileStatus =
  | "selected"
  | "uploaded"
  | "parsing"
  | "parsed"
  | "indexing"
  | "indexed"
  | "failed"

export interface KnowledgeFileItem {
  id: string
  source: File
  name: string
  size: number
  mimeType: string
  extension: string
  lastModified: number
  status: KnowledgeFileStatus
}

export type KnowledgePanelPresentation = "panel" | "drawer"
