import { apiClient } from "@/api/client"
import type {
  KnowledgeBase,
  KnowledgeChatResponse,
  KnowledgeEntitySearchResponse,
  KnowledgeExtractResult,
  KnowledgeFile,
  KnowledgeFileMarkdownResponse,
  KnowledgeGraphResponse,
  KnowledgeIndexResult,
} from "@/types/knowledge"

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
