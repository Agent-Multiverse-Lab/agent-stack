import { apiClient } from "@/api/client"

export interface SandboxWorkspaceResponse {
  thread_id: string
  sandbox_id: string
  status: string
  path: string
  entries: Array<{
    name: string
    path: string
    kind: "directory" | "file"
    size: number | null
    modified_at: string
    file_type?: "code" | "data" | "document" | "image" | null
  }>
}

export interface SandboxFileContentResponse {
  thread_id: string
  sandbox_id: string
  path: string
  content: string
  encoding: string
  truncated: boolean
}

/**
 * 列出指定会话沙箱工作区目录中的文件与子目录。
 * @param threadId 会话 ID。
 * @param path 目标目录路径，默认为 /workspace。
 * @returns 沙箱工作区状态及目录条目列表。
 */
export const listSandboxWorkspace = (threadId: string, path = "/workspace") => {
  const params = new URLSearchParams({ thread_id: threadId, path })
  return apiClient.apiGet<SandboxWorkspaceResponse>(
    `/api/sandbox/workspace?${params.toString()}`,
    { requiresAuth: true }
  )
}

/**
 * 读取沙箱工作区中的指定文件内容。
 * @param threadId 会话 ID。
 * @param path 文件路径。
 * @param editable 是否以可编辑模式读取，默认为 false。
 * @returns 文件文本内容、编码及是否截断标记。
 */
export const readSandboxFile = (threadId: string, path: string, editable = false) => {
  const params = new URLSearchParams({ thread_id: threadId, path })
  if (editable) params.set("editable", "true")
  return apiClient.apiGet<SandboxFileContentResponse>(
    `/api/sandbox/workspace/content?${params.toString()}`,
    { requiresAuth: true }
  )
}

/**
 * 下载沙箱工作区中的指定文件。
 * @param threadId 会话 ID。
 * @param path 文件路径。
 * @returns 文件二进制 Blob 对象。
 */
export const downloadSandboxFile = async (threadId: string, path: string): Promise<Blob> => {
  const params = new URLSearchParams({ thread_id: threadId, path })
  const response = await apiClient.apiFetch(
    `/api/sandbox/workspace/download?${params.toString()}`,
    { method: "GET", requiresAuth: true, cache: "no-store" },
  )
  return response.blob()
}

/**
 * 重命名沙箱工作区中的文件或目录。
 * @param threadId 会话 ID。
 * @param path 原文件或目录路径。
 * @param name 新的名称。
 * @returns 重命名后的目标路径。
 */
export const renameSandboxFile = (threadId: string, path: string, name: string) =>
  apiClient.apiPost<{ path: string }, { thread_id: string; path: string; name: string }>(
    "/api/sandbox/workspace/rename",
    { thread_id: threadId, path, name },
    { requiresAuth: true },
  )

/**
 * 更新沙箱工作区中的指定文件内容（带乐观并发校验）。
 * @param threadId 会话 ID。
 * @param path 目标文件路径。
 * @param content 新的文件内容。
 * @param previousContent 修改前的原始内容，用于冲突检测。
 */
export const updateSandboxFile = async (
  threadId: string, path: string, content: string, previousContent: string,
) => {
  await apiClient.apiFetch("/api/sandbox/workspace/content", {
    method: "PUT",
    requiresAuth: true,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id: threadId, path, content, previous_content: previousContent }),
  })
}

/**
 * 删除沙箱工作区中的指定文件或目录。
 * @param threadId 会话 ID。
 * @param path 目标文件或目录路径。
 * @returns 删除完成后的空响应。
 */
export const deleteSandboxFile = (threadId: string, path: string) => {
  const params = new URLSearchParams({ thread_id: threadId, path })
  return apiClient.apiDelete(`/api/sandbox/workspace/file?${params.toString()}`, { requiresAuth: true })
}

/**
 * 上传本地文件到指定会话的沙箱工作区目录。
 * @param threadId 会话 ID。
 * @param path 目标目录路径。
 * @param file 待上传的本地文件。
 * @returns 上传后新建的工作区文件条目信息。
 */
export const uploadSandboxFile = (
  threadId: string,
  path: string,
  file: File,
) => {
  const form = new FormData()
  form.append("thread_id", threadId)
  form.append("path", path)
  form.append("file", file)
  return apiClient.apiPost<SandboxWorkspaceResponse["entries"][number], FormData>(
    "/api/sandbox/workspace/upload",
    form,
    { requiresAuth: true },
  )
}

