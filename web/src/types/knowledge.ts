export type KnowledgeFileStatus =
  | "uploaded"
  | "parsing"
  | "parsed"
  | "indexing"
  | "indexed"
  | "extracting"
  | "extracted"
  | "failed"

export interface KnowledgeBase {
  kb_id: string
  name: string
  description: string
  status: string
}

export interface KnowledgeFile {
  file_id: string
  kb_id: string
  original_file_name: string
  original_object_name: string
  markdown_object_name: string | null
  content_type: string
  file_size: number
  status: KnowledgeFileStatus
  error_message: string | null
}

export interface KnowledgeIndexResult {
  kb_id: string
  file_id: string
  status: string
  chunk_count: number
  collection_name: string
  embedding_model_spec: string
  embedding_dimension: number
}

export interface KnowledgeExtractResult {
  kb_id: string
  file_id: string
  status: string
  entity_count: number
  relation_count: number
}

export interface KnowledgeGraphNode {
  entity_id: string
  name: string
  type: string
  description: string
  file_id: string
}

export interface KnowledgeGraphEdge {
  relation_id: string
  source_entity_id: string
  target_entity_id: string
  type: string
}

export interface KnowledgeGraphResponse {
  kb_id: string
  nodes: KnowledgeGraphNode[]
  edges: KnowledgeGraphEdge[]
  entity_count: number
  relation_count: number
}

export interface KnowledgeCitation {
  file_id: string
  file_name: string
  chunk_id: string
  excerpt: string
}

export interface KnowledgeChatResponse {
  kb_id: string
  answer: string
  citations: KnowledgeCitation[]
}

export interface KnowledgeEntityHit {
  entity_id: string
  name: string
  type: string
  description: string
  file_id: string
  similarity: number
}

export interface KnowledgeEntitySearchResponse {
  kb_id: string
  hits: KnowledgeEntityHit[]
}

export interface KnowledgeFileMarkdownResponse {
  file_id: string
  markdown: string
}
