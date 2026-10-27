import { apiClient } from "@/api/client"

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
  created_at?: string | null
  updated_at?: string | null
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

const encode = (value: string) => encodeURIComponent(value)

export const listKnowledgeBases = () =>
  apiClient.apiGet<KnowledgeBase[]>("/api/knowledge/bases", {
    requiresAuth: true
  })

export const getKnowledgeBase = (kbId: string) =>
  apiClient.apiGet<KnowledgeBase>(`/api/knowledge/bases/${encode(kbId)}`, {
    requiresAuth: true
  })

export const createKnowledgeBase = (payload: {
  name: string
  description: string
}) =>
  apiClient.apiPost<KnowledgeBase, typeof payload>(
    "/api/knowledge/bases",
    payload,
    { requiresAuth: true }
  )

export const deleteKnowledgeBase = (kbId: string) =>
  apiClient.apiDelete<{ kb_id: string; deleted_file_count: number }>(
    `/api/knowledge/bases/${encode(kbId)}`,
    { requiresAuth: true }
  )

export const listKnowledgeFiles = (kbId: string) =>
  apiClient.apiGet<KnowledgeFile[]>(
    `/api/knowledge/bases/${encode(kbId)}/files`,
    { requiresAuth: true }
  )

export const uploadKnowledgeFile = (kbId: string, file: File) => {
  const form = new FormData()
  form.append("file", file)
  return apiClient.apiPost<KnowledgeFile, FormData>(
    `/api/knowledge/bases/${encode(kbId)}/files`,
    form,
    { requiresAuth: true }
  )
}

export const deleteKnowledgeFile = (kbId: string, fileId: string) =>
  apiClient.apiDelete<{ file_id: string }>(
    `/api/knowledge/bases/${encode(kbId)}/files/${encode(fileId)}`,
    { requiresAuth: true }
  )

export const getKnowledgeFileMarkdown = (kbId: string, fileId: string) =>
  apiClient.apiGet<KnowledgeFileMarkdownResponse>(
    `/api/knowledge/bases/${encode(kbId)}/files/${encode(fileId)}/markdown`,
    { requiresAuth: true }
  )

export const parseKnowledgeFile = (kbId: string, fileId: string) =>
  apiClient.apiPost<KnowledgeFile, undefined>(
    `/api/knowledge/bases/${encode(kbId)}/files/${encode(fileId)}/parse`,
    undefined,
    { requiresAuth: true }
  )

export const indexKnowledgeFile = (kbId: string, fileId: string) =>
  apiClient.apiPost<KnowledgeIndexResult, undefined>(
    `/api/knowledge/bases/${encode(kbId)}/files/${encode(fileId)}/index`,
    undefined,
    { requiresAuth: true }
  )

export const extractKnowledgeFile = (kbId: string, fileId: string) =>
  apiClient.apiPost<KnowledgeExtractResult, undefined>(
    `/api/knowledge/bases/${encode(kbId)}/files/${encode(fileId)}/extract`,
    undefined,
    { requiresAuth: true }
  )

export const getKnowledgeGraph = (kbId: string) =>
  apiClient.apiGet<KnowledgeGraphResponse>(
    `/api/knowledge/bases/${encode(kbId)}/graph`,
    { requiresAuth: true }
  )

export const searchKnowledgeEntities = (
  kbId: string,
  query: string,
  limit = 20
) =>
  apiClient.apiPost<KnowledgeEntitySearchResponse, { query: string; limit: number }>(
    `/api/knowledge/bases/${encode(kbId)}/entities/search`,
    { query, limit },
    { requiresAuth: true }
  )

export const chatWithKnowledgeBase = (
  kbId: string,
  query: string,
  limit = 8
) =>
  apiClient.apiPost<KnowledgeChatResponse, { query: string; limit: number }>(
    `/api/knowledge/bases/${encode(kbId)}/chat`,
    { query, limit },
    { requiresAuth: true }
  )

export interface KnowledgeChunk {
  chunk_id: string
  chunk_index: number
  content: string
  metadata: Record<string, unknown>
}

export interface KnowledgeFileChunksResponse {
  file_id: string
  chunks: KnowledgeChunk[]
  has_more: boolean
}

export interface KnowledgeRerankInfo {
  applied: boolean
  model_spec: string
  candidate_count: number
  result_count: number
}

export interface KnowledgeChunkHit {
  chunk_id: string
  chunk_index: number
  file_id: string
  file_name: string
  content: string
  score: number | null
  rerank_score: number | null
  retrieval_rank: number | null
  rerank_rank: number | null
}

export interface KnowledgeChunkSearchResponse {
  kb_id: string
  hits: KnowledgeChunkHit[]
  rerank: KnowledgeRerankInfo | null
  embedding_model_spec: string
  embedding_dimension: number
}

export const getKnowledgeFileChunks = (
  kbId: string,
  fileId: string,
  limit = 20,
  offset = 0
) =>
  apiClient.apiGet<KnowledgeFileChunksResponse>(
    `/api/knowledge/bases/${encode(kbId)}/files/${encode(fileId)}/chunks?limit=${limit}&offset=${offset}`,
    { requiresAuth: true }
  )

export const searchKnowledgeChunks = (
  kbId: string,
  query: string,
  limit = 8
) =>
  apiClient.apiPost<
    KnowledgeChunkSearchResponse,
    { query: string; limit: number }
  >(
    `/api/knowledge/bases/${encode(kbId)}/search`,
    { query, limit },
    { requiresAuth: true }
  )
