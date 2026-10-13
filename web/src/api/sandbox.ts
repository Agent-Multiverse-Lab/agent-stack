import { apiClient } from "@/api/client"
import type {
  SandboxFileContentResponse,
  SandboxWorkspaceResponse,
} from "@/pages/sandbox/types"

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
