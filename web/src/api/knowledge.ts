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
  folder_id?: string | null
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

/**
 * 对 URL 路径片段进行 URI 编码。
 * @param value 原始路径参数值。
 * @returns 编码后的安全路径字符串。
 */
const encode = (value: string) => encodeURIComponent(value)

/**
 * 获取当前用户的所有知识库列表。
 * @returns 知识库列表。
 */
export const listKnowledgeBases = () =>
  apiClient.apiGet<KnowledgeBase[]>("/api/knowledge/bases", {
    requiresAuth: true
  })

/**
 * 获取指定知识库详情。
 * @param kbId 知识库 ID。
 * @returns 知识库信息。
 */
export const getKnowledgeBase = (kbId: string) =>
  apiClient.apiGet<KnowledgeBase>(`/api/knowledge/bases/${encode(kbId)}`, {
    requiresAuth: true
  })

/**
 * 创建新的知识库。
 * @param payload 知识库名称与描述。
 * @returns 新创建的知识库信息。
 */
export const createKnowledgeBase = (payload: {
  name: string
  description: string
}) =>
  apiClient.apiPost<KnowledgeBase, typeof payload>(
    "/api/knowledge/bases",
    payload,
    { requiresAuth: true }
  )

/**
 * 删除指定知识库及其关联文件。
 * @param kbId 知识库 ID。
 * @returns 被删除的知识库 ID 与文件数量。
 */
export const deleteKnowledgeBase = (kbId: string) =>
  apiClient.apiDelete<{ kb_id: string; deleted_file_count: number }>(
    `/api/knowledge/bases/${encode(kbId)}`,
    { requiresAuth: true }
  )

/**
 * 列出指定知识库下的全部文件。
 * @param kbId 知识库 ID。
 * @returns 知识库文件列表。
 */
export const listKnowledgeFiles = (kbId: string) =>
  apiClient.apiGet<KnowledgeFile[]>(
    `/api/knowledge/bases/${encode(kbId)}/files`,
    { requiresAuth: true }
  )

/**
 * 上传文件到指定知识库（可选放入指定文件夹）。
 * @param kbId 知识库 ID。
 * @param file 待上传的本地文件。
 * @param folderId 可选的目标文件夹 ID。
 * @returns 新上传的知识库文件记录。
 */
export const uploadKnowledgeFile = (kbId: string, file: File, folderId?: string | null) => {
  const form = new FormData()
  form.append("file", file)
  if (folderId) form.append("folder_id", folderId)
  return apiClient.apiPost<KnowledgeFile, FormData>(
    `/api/knowledge/bases/${encode(kbId)}/files`,
    form,
    { requiresAuth: true }
  )
}

/**
 * 删除知识库中的指定文件。
 * @param kbId 知识库 ID。
 * @param fileId 文件 ID。
 * @returns 已删除的文件 ID。
 */
export const deleteKnowledgeFile = (kbId: string, fileId: string) =>
  apiClient.apiDelete<{ file_id: string }>(
    `/api/knowledge/bases/${encode(kbId)}/files/${encode(fileId)}`,
    { requiresAuth: true }
  )

/**
 * 获取知识库文件解析后的 Markdown 内容。
 * @param kbId 知识库 ID。
 * @param fileId 文件 ID。
 * @returns 文件 ID 与 Markdown 文本。
 */
export const getKnowledgeFileMarkdown = (kbId: string, fileId: string) =>
  apiClient.apiGet<KnowledgeFileMarkdownResponse>(
    `/api/knowledge/bases/${encode(kbId)}/files/${encode(fileId)}/markdown`,
    { requiresAuth: true }
  )

/**
 * 触发对指定知识库文件的文档解析。
 * @param kbId 知识库 ID。
 * @param fileId 文件 ID。
 * @returns 更新状态后的文件信息。
 */
export const parseKnowledgeFile = (kbId: string, fileId: string) =>
  apiClient.apiPost<KnowledgeFile, undefined>(
    `/api/knowledge/bases/${encode(kbId)}/files/${encode(fileId)}/parse`,
    undefined,
    { requiresAuth: true }
  )

/**
 * 对已解析的知识库文件执行分块与向量索引。
 * @param kbId 知识库 ID。
 * @param fileId 文件 ID。
 * @returns 索引结果与分块统计信息。
 */
export const indexKnowledgeFile = (kbId: string, fileId: string) =>
  apiClient.apiPost<KnowledgeIndexResult, undefined>(
    `/api/knowledge/bases/${encode(kbId)}/files/${encode(fileId)}/index`,
    undefined,
    { requiresAuth: true }
  )

/**
 * 对指定知识库文件执行知识图谱实体与关系抽取。
 * @param kbId 知识库 ID。
 * @param fileId 文件 ID。
 * @returns 抽取出的实体和关系计数。
 */
export const extractKnowledgeFile = (kbId: string, fileId: string) =>
  apiClient.apiPost<KnowledgeExtractResult, undefined>(
    `/api/knowledge/bases/${encode(kbId)}/files/${encode(fileId)}/extract`,
    undefined,
    { requiresAuth: true }
  )

/**
 * 获取指定知识库的知识图谱节点与关系边。
 * @param kbId 知识库 ID。
 * @returns 图谱节点、边及数量统计。
 */
export const getKnowledgeGraph = (kbId: string) =>
  apiClient.apiGet<KnowledgeGraphResponse>(
    `/api/knowledge/bases/${encode(kbId)}/graph`,
    { requiresAuth: true }
  )

/**
 * 在知识库知识图谱中检索相似实体。
 * @param kbId 知识库 ID。
 * @param query 检索查询文本。
 * @param limit 返回结果上限，默认为 20。
 * @returns 命中的实体列表及相似度分数。
 */
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

/**
 * 基于知识库内容进行问答并返回带引用的回答。
 * @param kbId 知识库 ID。
 * @param query 用户提问文本。
 * @param limit 参与检索的上下文分块数量上限，默认为 8。
 * @returns 生成的回答及引用分块列表。
 */
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

/**
 * 分页获取指定知识库文件的分块列表。
 * @param kbId 知识库 ID。
 * @param fileId 文件 ID。
 * @param limit 每页返回的分块数量，默认为 20。
 * @param offset 分页偏移量，默认为 0。
 * @returns 分块列表及是否还有更多数据的标记。
 */
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

/**
 * 在知识库中执行向量语义检索（可选重排序）。
 * @param kbId 知识库 ID。
 * @param query 检索查询文本。
 * @param limit 可选的返回分块数量上限。
 * @param minScore 可选的最低相似度阈值。
 * @returns 命中的分块列表、重排序及嵌入模型信息。
 */
export const searchKnowledgeChunks = (
  kbId: string,
  query: string,
  limit?: number,
  minScore?: number
) =>
  apiClient.apiPost<
    KnowledgeChunkSearchResponse,
    { query: string; limit?: number; min_score?: number }
  >(
    `/api/knowledge/bases/${encode(kbId)}/search`,
    { query, limit, min_score: minScore },
    { requiresAuth: true }
  )


export interface KnowledgeSettings {
  chunker: "title" | "token"
  title_method: "hierarchy" | "group"
  target_level: number
  chunk_token_size: number
  embedding_model_spec: string | null
  top_k: number
  candidate_limit: number
  min_score: number | null
  rerank: boolean
}
export interface KnowledgeConfiguration extends KnowledgeBase {
  settings: KnowledgeSettings
  embedding_model_spec: string | null
}
export interface KnowledgeFolder { folder_id: string; parent_id: string | null; name: string }
export type KnowledgeOperation = "parse" | "index" | "extract" | "delete"
export interface KnowledgeTaskResult { file_id?: string; query?: string; success: boolean; error?: string; hit_count?: number }
export interface RetrievalReport {
  summary_by_k: { split: string; k: number; query_count: number; hit_rate: number; precision: number; recall: number; f1: number }[]
  selection: { recommended_top_k: number }
  queries: { query_id: string; query: string; relevant_chunk_ids: string[]; retrieved_chunk_ids: string[]; matched_chunk_ids: string[] }[]
}
export interface KnowledgeTask {
  task_id: string; kb_id: string; operation: KnowledgeOperation | "evaluate"
  status: "pending" | "running" | "completed" | "failed" | "cancelled"
  total: number; completed: number; results: KnowledgeTaskResult[]
  report: RetrievalReport | null; error: string | null
  created_at: string; finished_at: string | null
}
export interface KnowledgeEvaluationInput {
  dataset_id: string; dataset_version: string; corpus_version: string; ks: number[]
  samples: { query_id: string; query: string; split: "validation" | "test"; relevant_chunk_ids: string[] }[]
}
/**
 * 构建指定知识库的基础接口路径。
 * @param kbId 知识库 ID。
 * @returns 知识库资源基础路径。
 */
const workspacePath = (kbId: string) => `/api/knowledge/bases/${encode(kbId)}`
const auth = { requiresAuth: true }

/**
 * 获取指定知识库的分块与检索配置。
 * @param kbId 知识库 ID。
 * @returns 知识库配置详情。
 */
export const getKnowledgeSettings = (kbId: string) => apiClient.apiGet<KnowledgeConfiguration>(`${workspacePath(kbId)}/settings`, auth)

/**
 * 保存知识库的名称、描述与分块/检索参数配置。
 * @param kbId 知识库 ID。
 * @param value 待保存的知识库基础信息与设置。
 * @returns 更新后的知识库配置详情。
 */
export const saveKnowledgeSettings = (kbId: string, value: Pick<KnowledgeConfiguration, "name" | "description" | "settings">) => apiClient.apiPost<KnowledgeConfiguration, typeof value>(`${workspacePath(kbId)}/settings`, value, auth)

/**
 * 列出知识库中的全部文件夹。
 * @param kbId 知识库 ID。
 * @returns 文件夹列表。
 */
export const listKnowledgeFolders = (kbId: string) => apiClient.apiGet<KnowledgeFolder[]>(`${workspacePath(kbId)}/folders`, auth)

/**
 * 创建或更新知识库文件夹。
 * @param kbId 知识库 ID。
 * @param value 文件夹名称与父文件夹 ID。
 * @param folderId 可选的文件夹 ID；传入时更新现有文件夹，省略时新建。
 * @returns 保存后的文件夹信息。
 */
export const saveKnowledgeFolder = (kbId: string, value: { name: string; parent_id: string | null }, folderId?: string) => apiClient.apiPost<KnowledgeFolder, typeof value>(`${workspacePath(kbId)}/folders${folderId ? `/${encode(folderId)}` : ""}`, value, auth)

/**
 * 删除指定知识库文件夹。
 * @param kbId 知识库 ID。
 * @param folderId 文件夹 ID。
 * @returns 删除完成后的空响应。
 */
export const deleteKnowledgeFolder = (kbId: string, folderId: string) => apiClient.apiDelete(`${workspacePath(kbId)}/folders/${encode(folderId)}`, auth)

/**
 * 更新知识库文件的名称与所在文件夹。
 * @param kbId 知识库 ID。
 * @param fileId 文件 ID。
 * @param value 新的文件名与目标文件夹 ID（根目录为 null）。
 * @returns 更新结果。
 */
export const updateKnowledgeFile = (kbId: string, fileId: string, value: { name: string; folder_id: string | null }) => apiClient.apiPost<unknown, typeof value>(`${workspacePath(kbId)}/files/${encode(fileId)}/metadata`, value, auth)

/**
 * 列出指定知识库的后台处理与评测任务。
 * @param kbId 知识库 ID。
 * @returns 任务列表。
 */
export const listKnowledgeTasks = (kbId: string) => apiClient.apiGet<KnowledgeTask[]>(`${workspacePath(kbId)}/tasks`, auth)

/**
 * 批量启动知识库文件异步任务（解析、索引、抽取或删除）。
 * @param kbId 知识库 ID。
 * @param operation 任务操作类型。
 * @param fileIds 目标文件 ID 列表。
 * @returns 新创建的任务状态信息。
 */
export const startKnowledgeTask = (kbId: string, operation: KnowledgeOperation, fileIds: string[]) => apiClient.apiPost<KnowledgeTask, { operation: KnowledgeOperation; file_ids: string[] }>(`${workspacePath(kbId)}/tasks`, {operation, file_ids: fileIds}, auth)

/**
 * 取消指定知识库任务。
 * @param kbId 知识库 ID。
 * @param taskId 任务 ID。
 * @returns 更新状态后的任务信息。
 */
export const cancelKnowledgeTask = (kbId: string, taskId: string) => apiClient.apiPost<KnowledgeTask, undefined>(`${workspacePath(kbId)}/tasks/${encode(taskId)}/cancel`, undefined, auth)

/**
 * 提交评测数据集并启动知识库检索效果评测任务。
 * @param kbId 知识库 ID。
 * @param payload 评测数据集版本、K 值列表及样本集合。
 * @returns 新创建的评测任务信息。
 */
export const startKnowledgeEvaluation = (kbId: string, payload: KnowledgeEvaluationInput) => apiClient.apiPost<KnowledgeTask, KnowledgeEvaluationInput>(`${workspacePath(kbId)}/evaluations`, payload, auth)

/**
 * 从知识库下载指定原始文件并触发浏览器保存。
 * @param kbId 知识库 ID。
 * @param file 目标知识库文件对象。
 */
export async function downloadKnowledgeFile(kbId: string, file: KnowledgeFile) {
  const response = await apiClient.apiFetch(`${workspacePath(kbId)}/files/${encode(file.file_id)}/download`, auth)
  saveKnowledgeDownload(await response.blob(), file.original_file_name)
}

/**
 * 通过临时 Object URL 在浏览器中触发 Blob 文件下载。
 * @param blob 待下载的文件二进制对象。
 * @param name 保存的文件名。
 */
export function saveKnowledgeDownload(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url; link.download = name; link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
