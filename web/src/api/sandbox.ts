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

export const listSandboxWorkspace = (threadId: string, path = "/workspace") => {
  const params = new URLSearchParams({ thread_id: threadId, path })
  return apiClient.apiGet<SandboxWorkspaceResponse>(
    `/api/sandbox/workspace?${params.toString()}`,
    { requiresAuth: true }
  )
}

export const readSandboxFile = (threadId: string, path: string, editable = false) => {
  const params = new URLSearchParams({ thread_id: threadId, path })
  if (editable) params.set("editable", "true")
  return apiClient.apiGet<SandboxFileContentResponse>(
    `/api/sandbox/workspace/content?${params.toString()}`,
    { requiresAuth: true }
  )
}

export const downloadSandboxFile = async (threadId: string, path: string): Promise<Blob> => {
  const params = new URLSearchParams({ thread_id: threadId, path })
  const response = await apiClient.apiFetch(
    `/api/sandbox/workspace/download?${params.toString()}`,
    { method: "GET", requiresAuth: true, cache: "no-store" },
  )
  return response.blob()
}

export const renameSandboxFile = (threadId: string, path: string, name: string) =>
  apiClient.apiPost<{ path: string }, { thread_id: string; path: string; name: string }>(
    "/api/sandbox/workspace/rename",
    { thread_id: threadId, path, name },
    { requiresAuth: true },
  )

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

export const deleteSandboxFile = (threadId: string, path: string) => {
  const params = new URLSearchParams({ thread_id: threadId, path })
  return apiClient.apiDelete(`/api/sandbox/workspace/file?${params.toString()}`, { requiresAuth: true })
}

